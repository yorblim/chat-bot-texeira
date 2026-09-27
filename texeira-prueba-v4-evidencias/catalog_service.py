"""
catalog_service.py — Servicio de Catálogo Dinámico para Texeira Travel.

Permite al personal de la agencia gestionar tours, precios oficiales,
horarios vigentes, descripciones, inclusiones y archivos multimedia
(fotos y folletos PDF) en tiempo real, con persistencia garantizada
en PostgreSQL (Neon) o SQLite local, e integración directa al motor RAG.
"""

import os
import json
import time
import base64
import hashlib
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

from db_adapter import get_db_session, is_postgres

ROOT_DIR = Path(__file__).resolve().parent
CATALOG_JSON_PATH = ROOT_DIR / "data" / "tours_catalog.json"
IMAGES_DIR = ROOT_DIR / "data" / "images"
BROCHURES_DIR = ROOT_DIR / "data" / "brochures"

# Asegurar directorios
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
BROCHURES_DIR.mkdir(parents=True, exist_ok=True)

# Caché en memoria para respuesta rápida con sincronización de versión
_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_LAST_DB_UPDATE: str = ""

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS catalog_tours (
    entity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    official_price TEXT DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'USD',
    schedule TEXT DEFAULT '',
    duration TEXT DEFAULT '',
    includes TEXT DEFAULT '',
    excludes TEXT DEFAULT '',
    photo_filename TEXT DEFAULT '',
    photo_data BLOB,
    brochure_filename TEXT DEFAULT '',
    brochure_data BLOB,
    is_canonical INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS catalog_tours (
    entity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    official_price TEXT DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'USD',
    schedule TEXT DEFAULT '',
    duration TEXT DEFAULT '',
    includes TEXT DEFAULT '',
    excludes TEXT DEFAULT '',
    photo_filename TEXT DEFAULT '',
    photo_data BYTEA,
    brochure_filename TEXT DEFAULT '',
    brochure_data BYTEA,
    is_canonical INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SCHEMA_RATES_SQLITE = """
CREATE TABLE IF NOT EXISTS catalog_tour_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    rate_category TEXT NOT NULL DEFAULT 'custom',
    rate_name TEXT NOT NULL,
    price TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    conditions TEXT DEFAULT '',
    valid_from TEXT DEFAULT '',
    valid_to TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SCHEMA_RATES_POSTGRES = """
CREATE TABLE IF NOT EXISTS catalog_tour_rates (
    id SERIAL PRIMARY KEY,
    entity_id TEXT NOT NULL,
    rate_category TEXT NOT NULL DEFAULT 'custom',
    rate_name TEXT NOT NULL,
    price TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    conditions TEXT DEFAULT '',
    valid_from TEXT DEFAULT '',
    valid_to TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Alias iniciales de tours canónicos de Texeira Travel
INITIAL_CANONICAL_ALIASES = {
    'city-tour-cusco': ['city tour', 'citytour', 'city-tour', 'tour cusco', 'tour de cusco'],
    'valle-sagrado': ['valle sagrado', 'sacred valley'],
    'machu-picchu-tren': ['machu picchu en tren', 'machupicchu tren', 'machu picchu'],
    'machu-picchu-car': ['machu picchu by car', 'machu picchu en auto', 'machu picchu en carro'],
    'valle-sur': ['valle sur', 'south valley'],
    'montana-7-colores': ['montana de 7 colores', '7 colores', 'rainbow mountain', 'vinicunca', 'valle rojo'],
    'laguna-humantay': ['humantay', 'laguna humantay'],
    'waqra-pukara': ['waqra pukara', 'huaccra pukara'],
    'maras-moray': ['maras moray', 'maras-moray', 'moray maras'],
    'maras-moray-cuatrimoto': ['cuatrimoto', 'cuatrimotos', 'atv maras'],
    'camino-inka': ['camino inka', 'camino inca', 'inka trail'],
    'salkantay-trek': ['salkantay', 'salkantay trek'],
    'inka-jungle': ['inka jungle', 'inca jungle'],
    'choquequirao': ['choquequirao'],
    'tour-mistico': ['tour mistico', 'mistico', 'mystic'],
    'islas-titicaca': ['titicaca', 'islas del titicaca', 'uros', 'taquile'],
    'canon-colca': ['canon del colca', 'colca', 'baños termales'],
    'ruta-del-sol': ['ruta del sol', 'cusco puno', 'cusco a puno'],
    'puente-qeswachaca': ['qeswachaca', 'puente qeswachaca', 'queswachaca'],
}


def init_catalog_db() -> None:
    """Crea las tablas catalog_tours y catalog_tour_rates y migra los tours canónicos si está vacía."""
    schema = SCHEMA_POSTGRES if is_postgres() else SCHEMA_SQLITE
    schema_rates = SCHEMA_RATES_POSTGRES if is_postgres() else SCHEMA_RATES_SQLITE
    with get_db_session() as conn:
        conn.execute(schema)
        conn.execute(schema_rates)
        conn.execute("""CREATE TABLE IF NOT EXISTS catalog_field_overrides (
            entity_id TEXT NOT NULL, field TEXT NOT NULL,
            PRIMARY KEY (entity_id, field)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tour_rates_entity ON catalog_tour_rates(entity_id)")
        # Verificar si ya existen tours
        cur = conn.execute("SELECT COUNT(*) FROM catalog_tours")
        row = cur.fetchone()
        count = row[0] if row else 0

        if count == 0:
            print("[CATALOG SERVICE] Inicializando catálogo desde tours_catalog.json...")
            _seed_from_json(conn)


def _seed_from_json(conn) -> None:
    """Inserta los 19 tours canónicos iniciales a partir del catálogo JSON."""
    if not CATALOG_JSON_PATH.exists():
        return

    try:
        with open(CATALOG_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = datetime.utcnow().isoformat()
        tours = data.get("tours", [])
        for t in tours:
            eid = t.get("entity_id", "")
            if not eid:
                continue

            name = t.get("name", eid)
            aliases = INITIAL_CANONICAL_ALIASES.get(eid, [name.lower()])
            price = str(t.get("official_price", "") or "")
            curr = str(t.get("currency", "USD"))
            # Los tours canónicos iniciales no tienen sobreescritura de horario administrativo;
            # se gestionan mediante hechos históricos hasta que la agencia los actualice dinámicamente.
            sched = ""
            dur = str(t.get("duration", "") or "")
            inc = str(t.get("includes_note", "") or "")
            exc = str(t.get("excludes_note", "") or "")

            # Revisar si tiene imagen asociada
            photo_file = ""
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                candidate = IMAGES_DIR / f"{eid}{ext}"
                if candidate.exists():
                    photo_file = candidate.name
                    break

            conn.execute(
                """
                INSERT INTO catalog_tours (
                    entity_id, name, aliases, official_price, currency,
                    schedule, duration, includes, excludes, photo_filename,
                    is_canonical, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    eid, name, json.dumps(aliases), price, curr,
                    sched, dur, inc, exc, photo_file, now, now
                )
            )
        print(f"[CATALOG SERVICE] Se registraron {len(tours)} tours canónicos en la base de datos.")
    except Exception as e:
        print(f"[CATALOG SERVICE ERROR] Fallo al sembrar catálogo canónico: {e}")


def invalidate_catalog_cache() -> None:
    """Invalida la caché en memoria para forzar recarga."""
    global _CATALOG_CACHE, _CACHE_TIMESTAMP, _CACHE_LAST_DB_UPDATE
    _CATALOG_CACHE = None
    _CACHE_TIMESTAMP = 0.0
    _CACHE_LAST_DB_UPDATE = ""


def _get_db_latest_update() -> str:
    """Consulta la última fecha de actualización registrada en la base de datos."""
    try:
        with get_db_session() as conn:
            cur = conn.execute("SELECT MAX(updated_at) FROM catalog_tours")
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return ""


def get_all_tours(active_only: bool = True, strict: bool = False) -> List[Dict[str, Any]]:
    """Retorna la lista de tours desde la base de datos con invalidación verificable."""
    global _CATALOG_CACHE, _CACHE_TIMESTAMP, _CACHE_LAST_DB_UPDATE
    now = time.time()

    # Si tenemos caché en memoria, verificar si la versión en DB cambió
    db_update = _get_db_latest_update()
    if _CATALOG_CACHE is not None and (now - _CACHE_TIMESTAMP) < 1.0:
        if db_update and db_update == _CACHE_LAST_DB_UPDATE:
            tours = list(_CATALOG_CACHE.values())
            if active_only:
                return [t for t in tours if t.get("is_active", 1)]
            return tours

    try:
        init_catalog_db()
        with get_db_session() as conn:
            cur = conn.execute(
                """
                SELECT entity_id, name, aliases, official_price, currency,
                       schedule, duration, includes, excludes, photo_filename,
                       brochure_filename, is_canonical, is_active, created_at, updated_at
                FROM catalog_tours
                ORDER BY is_canonical DESC, name ASC
                """
            )
            rows = cur.fetchall()

            overrides = {}
            for row in conn.execute("SELECT entity_id, field FROM catalog_field_overrides").fetchall():
                overrides.setdefault(row[0], []).append(row[1])

        cache = {}
        for r in rows:
            aliases_raw = r["aliases"] if isinstance(r, dict) or hasattr(r, "__getitem__") else r[2]
            try:
                aliases_list = json.loads(aliases_raw) if isinstance(aliases_raw, str) else list(aliases_raw)
            except Exception:
                aliases_list = []

            item = {
                "entity_id": r["entity_id"],
                "name": r["name"],
                "aliases": aliases_list,
                "official_price": r["official_price"] or "",
                "currency": r["currency"] or "USD",
                "schedule": r["schedule"] or "",
                "duration": r["duration"] or "",
                "includes": r["includes"] or "",
                "excludes": r["excludes"] or "",
                "photo_filename": r["photo_filename"] or "",
                "brochure_filename": r["brochure_filename"] or "",
                "is_canonical": bool(r["is_canonical"]),
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "overridden_fields": overrides.get(r["entity_id"], []),
            }
            cache[item["entity_id"]] = item

        _CATALOG_CACHE = cache
        _CACHE_TIMESTAMP = now
        _CACHE_LAST_DB_UPDATE = db_update or max((item["updated_at"] for item in cache.values()), default="")

        tours = list(cache.values())
        if active_only:
            return [t for t in tours if t.get("is_active", 1)]
        return tours
    except Exception as e:
        print(f"[CATALOG SERVICE ERROR] Error consultando tours: {e}")
        if strict:
            raise
        return []


def get_tour_by_id(entity_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene un tour específico por su entity_id."""
    tours = get_all_tours(active_only=False)
    for t in tours:
        if t["entity_id"] == entity_id:
            return t
    return None


get_tour = get_tour_by_id


def upsert_tour(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Crea o actualiza un tour en la base de datos.
    Valida campos obligatorios y normaliza entity_id.
    """
    entity_id = str(data.get("entity_id", "")).strip().lower()
    name = str(data.get("name", "")).strip()

    if not entity_id or not name:
        return False, "El identificador (entity_id) y el nombre son obligatorios."

    # Normalizar entity_id para URLs y claves
    import re
    clean_id = re.sub(r"[^\w\-]", "-", entity_id).strip("-")
    if not clean_id:
        return False, "Identificador de tour inválido."

    supplied_fields = set(data)
    previous = get_tour_by_id(clean_id)
    if previous:
        data = {**previous, **data}

    aliases = data.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [a.strip() for a in aliases.split(",") if a.strip()]
    else:
        aliases = list(aliases)
    if name.lower() not in [a.lower() for a in aliases]:
        aliases.append(name.lower())

    price = str(data.get("official_price", "") or "").strip()
    currency = str(data.get("currency", "USD")).strip().upper()
    schedule = str(data.get("schedule", "") or "").strip()
    duration = str(data.get("duration", "") or "").strip()
    includes = str(data.get("includes", "") or "").strip()
    excludes = str(data.get("excludes", "") or "").strip()
    is_active = 1 if data.get("is_active", True) else 0

    now = datetime.utcnow().isoformat()

    try:
        init_catalog_db()
        with get_db_session() as conn:
            existing = conn.execute(
                "SELECT is_canonical, photo_filename, brochure_filename FROM catalog_tours WHERE entity_id = ?",
                (clean_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE catalog_tours
                    SET name = ?, aliases = ?, official_price = ?, currency = ?,
                        schedule = ?, duration = ?, includes = ?, excludes = ?,
                        is_active = ?, updated_at = ?
                    WHERE entity_id = ?
                    """,
                    (
                        name, json.dumps(aliases), price, currency,
                        schedule, duration, includes, excludes,
                        is_active, now, clean_id
                    )
                )
            else:
                conn.execute(
                    """
                    INSERT INTO catalog_tours (
                        entity_id, name, aliases, official_price, currency,
                        schedule, duration, includes, excludes,
                        is_canonical, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        clean_id, name, json.dumps(aliases), price, currency,
                        schedule, duration, includes, excludes,
                        is_active, now, now
                    )
                )

            # Registrar una edición explícita, incluso cuando la agencia borra
            # el valor. Un vacío administrativo no debe resucitar el folleto.
            for field in ('official_price', 'schedule', 'duration', 'includes', 'excludes'):
                if field in supplied_fields:
                    conn.execute("""INSERT INTO catalog_field_overrides (entity_id, field)
                                    VALUES (?, ?) ON CONFLICT (entity_id, field) DO NOTHING""",
                                 (clean_id, field))

        invalidate_catalog_cache()

        return True, clean_id
    except Exception as e:
        print(f"[CATALOG SERVICE ERROR] Error guardando tour {clean_id}: {e}")
        return False, str(e)


save_tour = upsert_tour


def save_asset(
    entity_id: str,
    asset_type: str,
    filename: str,
    content_bytes: bytes,
) -> Tuple[bool, str]:
    """
    Guarda una imagen o folleto tanto en disco como en PostgreSQL/SQLite (BLOB/BYTEA).
    Aplica versionado verificable por hash de contenido para prevenir que réplicas
    o instancias independientes sirvan copias multimedia obsoletas.
    Retorna (éxito, nombre_del_archivo_guardado).
    """
    if asset_type not in ("photo", "brochure"):
        return False, "Tipo de asset no válido (debe ser photo o brochure)."

    import re
    # Normalizar extensión segura
    ext = os.path.splitext(filename)[1].lower()
    if asset_type == "photo" and ext not in (".jpg", ".jpeg", ".png", ".webp"):
        return False, "Formato de imagen no permitido (use JPG, PNG o WebP)."
    if asset_type == "brochure" and ext != ".pdf":
        return False, "El folleto debe ser un archivo PDF."

    # Versionado determinista e inmutable basado en el hash del contenido
    content_hash = hashlib.sha256(content_bytes).hexdigest()[:10]
    safe_filename = f"{entity_id}_{asset_type}_{content_hash}{ext}"

    # 1. Guardar en disco para acceso estático inmediato
    target_dir = IMAGES_DIR if asset_type == "photo" else BROCHURES_DIR
    target_path = target_dir / safe_filename

    # Eliminar versiones locales obsoletas del mismo tour y tipo de asset
    try:
        for old_file in target_dir.glob(f"{entity_id}_{asset_type}_*{ext}"):
            if old_file.name != safe_filename:
                try:
                    old_file.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    try:
        with open(target_path, "wb") as f:
            f.write(content_bytes)
    except Exception as e:
        print(f"[CATALOG ASSET ERROR] No se pudo guardar en disco: {e}")

    # 2. Guardar en Base de Datos para durabilidad permanente en Cloud Run y sincronización multi-instancia
    now = datetime.utcnow().isoformat()
    try:
        init_catalog_db()
        with get_db_session() as conn:
            if asset_type == "photo":
                conn.execute(
                    """
                    UPDATE catalog_tours
                    SET photo_filename = ?, photo_data = ?, updated_at = ?
                    WHERE entity_id = ?
                    """,
                    (safe_filename, content_bytes, now, entity_id)
                )
            else:
                conn.execute(
                    """
                    UPDATE catalog_tours
                    SET brochure_filename = ?, brochure_data = ?, updated_at = ?
                    WHERE entity_id = ?
                    """,
                    (safe_filename, content_bytes, now, entity_id)
                )

        invalidate_catalog_cache()
        return True, safe_filename
    except Exception as e:
        print(f"[CATALOG ASSET ERROR] Error guardando asset en DB: {e}")
        return False, str(e)


save_tour_asset = save_asset


def get_asset_bytes(filename: str, asset_type: str) -> Optional[Tuple[bytes, str]]:
    """
    Recupera los bytes de una foto o folleto.
    Primero busca en disco; si no existe (ej. nueva réplica en Cloud Run o actualización
    desde otra instancia), lo descarga de la base de datos y lo almacena en disco.
    """
    target_dir = IMAGES_DIR if asset_type == "photo" else BROCHURES_DIR
    local_path = target_dir / filename

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }
    ext = os.path.splitext(filename)[1].lower()
    content_type = mime_types.get(ext, "application/octet-stream")

    col_name = "photo_filename" if asset_type == "photo" else "brochure_filename"
    col_data = "photo_data" if asset_type == "photo" else "brochure_data"

    if local_path.exists():
        try:
            return local_path.read_bytes(), content_type
        except Exception:
            pass

    # Si no está en disco (ej. otra réplica), consultar en la Base de Datos
    try:
        with get_db_session() as conn:
            cur = conn.execute(
                f"SELECT {col_data} FROM catalog_tours WHERE {col_name} = ?",
                (filename,)
            )
            row = cur.fetchone()
            if row and row[0]:
                data = row[0]
                if isinstance(data, memoryview):
                    data = data.tobytes()
                # Cachear en disco para próximas consultas de esta réplica
                try:
                    local_path.write_bytes(data)
                except Exception:
                    pass
                return data, content_type
    except Exception as e:
        print(f"[CATALOG ASSET ERROR] Error leyendo asset de DB: {e}")

    return None


def delete_tour(entity_id: str) -> Tuple[bool, str]:
    """
    Elimina un tour personalizado o desactiva un tour canónico.
    Los 19 tours canónicos nunca se borran físicamente para proteger la tesis.
    """
    try:
        init_catalog_db()
        with get_db_session() as conn:
            row = conn.execute(
                "SELECT is_canonical FROM catalog_tours WHERE entity_id = ?",
                (entity_id,)
            ).fetchone()
            if not row:
                return False, "Tour no encontrado."

            is_canonical = row["is_canonical"] if hasattr(row, "__getitem__") else row[0]
            if is_canonical:
                # Los canónicos solo se marcan como inactivos
                conn.execute(
                    "UPDATE catalog_tours SET is_active = 0, updated_at = ? WHERE entity_id = ?",
                    (datetime.utcnow().isoformat(), entity_id)
                )
                invalidate_catalog_cache()
                return True, "Tour canónico desactivado."
            else:
                for p in IMAGES_DIR.glob(f"{entity_id}_*"):
                    try:
                        p.unlink()
                    except Exception:
                        pass
                for b in BROCHURES_DIR.glob(f"{entity_id}_*"):
                    try:
                        b.unlink()
                    except Exception:
                        pass
                conn.execute("DELETE FROM catalog_tour_rates WHERE entity_id = ?", (entity_id,))
                conn.execute("DELETE FROM catalog_field_overrides WHERE entity_id = ?", (entity_id,))
                conn.execute("DELETE FROM catalog_tours WHERE entity_id = ?", (entity_id,))
                invalidate_catalog_cache()
                return True, "Tour personalizado eliminado."
    except Exception as e:
        return False, str(e)


def get_active_entity_keywords() -> Dict[str, List[str]]:
    """
    Retorna un diccionario de {entity_id: [keywords]} ÚNICAMENTE con los tours activos.
    Si un tour canónico o dinámico está desactivado, sus palabras clave NO se devuelven.
    Se utiliza en detect_entity_from_question() para soporte RAG en vivo.
    """
    active_tours = get_all_tours(active_only=True)
    active_eids = {t["entity_id"] for t in active_tours}
    keywords_map = {}
    for eid, initial_kw in INITIAL_CANONICAL_ALIASES.items():
        if eid in active_eids:
            keywords_map[eid] = list(initial_kw)
    for t in active_tours:
        eid = t["entity_id"]
        aliases = t.get("aliases", [])
        name = t.get("name", "")
        existing = keywords_map.get(eid, [])
        all_kw = list(existing) + list(aliases)
        if name and name not in all_kw:
            all_kw.append(name)
        combined = list(dict.fromkeys(all_kw))
        keywords_map[eid] = combined
    return keywords_map


# ============================================================
# GESTIÓN DE TARIFAS ESPECIALES Y FLEXIBLES (Tour hasMany Rates)
# ============================================================

def get_tour_rates(
    entity_id: str,
    active_only: bool = True,
    date_str: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retorna las tarifas especiales asociadas a un tour (entity_id).
    Permite filtrar por activas y por ventana de vigencia (valid_from / valid_to).
    Si date_str es None, se toma la fecha actual UTC en formato YYYY-MM-DD.
    """
    try:
        init_catalog_db()
        with get_db_session() as conn:
            cur = conn.execute(
                """
                SELECT id, entity_id, rate_category, rate_name, price, currency,
                       conditions, valid_from, valid_to, is_active, created_at, updated_at
                FROM catalog_tour_rates
                WHERE entity_id = ?
                ORDER BY id ASC
                """,
                (entity_id,)
            )
            rows = cur.fetchall()

        if date_str is None:
            date_str = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()

        rates = []
        for r in rows:
            is_act = bool(r["is_active"] if hasattr(r, "__getitem__") else r[9])
            if active_only and not is_act:
                continue

            v_from = str((r["valid_from"] if hasattr(r, "__getitem__") else r[7]) or "").strip()
            v_to = str((r["valid_to"] if hasattr(r, "__getitem__") else r[8]) or "").strip()

            # Validación de ventana de vigencia si está activa y se solicita filtrado por fecha
            if active_only:
                if v_from and date_str < v_from:
                    continue  # Aún no entra en vigencia
                if v_to and date_str > v_to:
                    continue  # Ya venció

            item = {
                "id": r["id"] if hasattr(r, "__getitem__") else r[0],
                "entity_id": r["entity_id"] if hasattr(r, "__getitem__") else r[1],
                "rate_category": r["rate_category"] if hasattr(r, "__getitem__") else r[2],
                "rate_name": r["rate_name"] if hasattr(r, "__getitem__") else r[3],
                "price": str(r["price"] if hasattr(r, "__getitem__") else r[4]),
                "currency": r["currency"] if hasattr(r, "__getitem__") else r[5],
                "conditions": (r["conditions"] if hasattr(r, "__getitem__") else r[6]) or "",
                "valid_from": v_from,
                "valid_to": v_to,
                "is_active": is_act,
                "created_at": r["created_at"] if hasattr(r, "__getitem__") else r[10],
                "updated_at": r["updated_at"] if hasattr(r, "__getitem__") else r[11],
            }
            rates.append(item)
        return rates
    except Exception as e:
        print(f"[CATALOG SERVICE ERROR] Error consultando tarifas de {entity_id}: {e}")
        return []


def upsert_tour_rate(data: Dict[str, Any]) -> Tuple[bool, Union[int, str]]:
    """
    Crea o actualiza una tarifa especial para un tour.
    Retorna (ok: bool, rate_id_o_mensaje: Union[int, str]).
    """
    if not isinstance(data, dict):
        return False, "La tarifa debe ser un objeto."
    entity_id = str(data.get("entity_id") or "").strip().lower()
    rate_name = str(data.get("rate_name") or data.get("name") or "").strip()
    price = str(data.get("price", "")).strip()

    if not entity_id or not rate_name or not price:
        return False, "El entity_id, nombre de tarifa y precio son obligatorios."

    rate_category = str(data.get("rate_category") or data.get("category") or "custom").strip().lower()
    allowed_categories = {"adult", "student", "child", "promo", "custom"}
    if rate_category not in allowed_categories:
        return False, "Categoría de tarifa inválida."

    currency = str(data.get("currency", "USD")).strip().upper()
    conditions = str(data.get("conditions", "") or "").strip()
    valid_from = str(data.get("valid_from", "") or "").strip()
    valid_to = str(data.get("valid_to", "") or "").strip()
    active = data.get("is_active", True)
    if type(active) not in (bool, int) or active not in (0, 1):
        return False, "is_active debe ser booleano o 0/1."
    is_active = int(active)
    if currency not in {"USD", "PEN"}:
        return False, "Moneda inválida; use USD o PEN."
    try:
        amount = Decimal(price)
        if not amount.is_finite() or amount < 0:
            return False, "El precio debe ser un número finito no negativo."
        for value in (valid_from, valid_to):
            if value and date.fromisoformat(value).isoformat() != value:
                return False, "Fecha inválida; use YYYY-MM-DD."
        if valid_from and valid_to and valid_from > valid_to:
            return False, "El inicio de vigencia no puede ser posterior al final."
    except (InvalidOperation, ValueError):
        return False, "Precio o fecha inválidos."

    rate_id = data.get("id")
    now = datetime.utcnow().isoformat()

    try:
        init_catalog_db()
        with get_db_session() as conn:
            if rate_id:
                rate_id_int = int(rate_id)
                if not conn.execute("SELECT id FROM catalog_tour_rates WHERE id = ? AND entity_id = ?",
                                    (rate_id_int, entity_id)).fetchone():
                    return False, "Tarifa no encontrada para este tour."
                conn.execute(
                    """
                    UPDATE catalog_tour_rates
                    SET rate_category = ?, rate_name = ?, price = ?, currency = ?,
                        conditions = ?, valid_from = ?, valid_to = ?, is_active = ?, updated_at = ?
                    WHERE id = ? AND entity_id = ?
                    """,
                    (
                        rate_category, rate_name, price, currency,
                        conditions, valid_from, valid_to, is_active, now,
                        rate_id_int, entity_id
                    )
                )
                final_id = rate_id_int
            else:
                if not conn.execute("SELECT entity_id FROM catalog_tours WHERE entity_id = ?", (entity_id,)).fetchone():
                    return False, "Tour no encontrado."
                cur = conn.execute(
                    """
                    INSERT INTO catalog_tour_rates (
                        entity_id, rate_category, rate_name, price, currency,
                        conditions, valid_from, valid_to, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_id, rate_category, rate_name, price, currency,
                        conditions, valid_from, valid_to, is_active, now, now
                    )
                )
                final_id = cur.lastrowid
                if final_id is None:
                    raise RuntimeError("La base de datos no devolvió el ID de la tarifa.")

            # Tocar updated_at del tour padre para forzar sincronización instantánea de caché
            conn.execute(
                "UPDATE catalog_tours SET updated_at = ? WHERE entity_id = ?",
                (now, entity_id)
            )

        invalidate_catalog_cache()
        return True, final_id
    except Exception as e:
        print(f"[CATALOG SERVICE ERROR] Error guardando tarifa para {entity_id}: {e}")
        return False, str(e)


def delete_tour_rate(rate_id: int, entity_id: Optional[str] = None) -> Tuple[bool, str]:
    """Elimina una tarifa especial por su ID."""
    try:
        init_catalog_db()
        now = datetime.utcnow().isoformat()
        with get_db_session() as conn:
            existing = conn.execute("SELECT entity_id FROM catalog_tour_rates WHERE id = ?", (rate_id,)).fetchone()
            if not existing or (entity_id and existing[0] != entity_id):
                return False, "Tarifa no encontrada para este tour."
            if entity_id:
                conn.execute(
                    "DELETE FROM catalog_tour_rates WHERE id = ? AND entity_id = ?",
                    (rate_id, entity_id)
                )
                conn.execute(
                    "UPDATE catalog_tours SET updated_at = ? WHERE entity_id = ?",
                    (now, entity_id)
                )
            else:
                row = conn.execute(
                    "SELECT entity_id FROM catalog_tour_rates WHERE id = ?",
                    (rate_id,)
                ).fetchone()
                eid = row[0] if row else ""
                conn.execute("DELETE FROM catalog_tour_rates WHERE id = ?", (rate_id,))
                if eid:
                    conn.execute(
                        "UPDATE catalog_tours SET updated_at = ? WHERE entity_id = ?",
                        (now, eid)
                    )

        invalidate_catalog_cache()
        return True, "Tarifa eliminada exitosamente."
    except Exception as e:
        return False, str(e)
