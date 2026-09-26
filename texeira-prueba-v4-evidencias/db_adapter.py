"""
db_adapter.py — Capa de persistencia universal (PostgreSQL vía DATABASE_URL o SQLite local).

Selecciona PostgreSQL remoto cuando está configurado, o SQLite para uso local.
La configuración del proveedor y la durabilidad del trabajo se validan por separado.
"""

import os
import re
import ssl
import socket
import sqlite3
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

import pg8000.core
import pg8000.dbapi
import pg8000.exceptions
from pg8000.core import i_unpack, NULL_BYTE

logger = logging.getLogger(__name__)

_ENGINE = None
_PG_INITIALIZED = False

WEBHOOK_RECEIPTS_SCHEMA = """CREATE TABLE IF NOT EXISTS webhook_receipts (
    message_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    status TEXT NOT NULL, owner TEXT NOT NULL, lease_until DOUBLE PRECISION NOT NULL
)"""


def is_postgres() -> bool:
    """Retorna True si DATABASE_URL está configurada para PostgreSQL."""
    url = os.getenv("DATABASE_URL", "").strip()
    return bool(url and (url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+")))


def sanitize_error_message(msg: str, secret: Optional[Union[str, bytes]] = None) -> str:
    """
    Elimina contraseñas, URLs con credenciales y datos sensibles de mensajes de error.
    Garantiza que ninguna credencial quede expuesta en logs o excepciones.
    """
    if not msg:
        return ""
    sanitized = str(msg)
    if isinstance(secret, bytes):
        secret = secret.decode("utf-8", errors="ignore")
    if secret and len(secret) > 0 and secret in sanitized:
        sanitized = sanitized.replace(secret, "***")
    # Enmascarar credenciales tipo postgresql://usuario:contraseña@host o user:pass@host
    sanitized = re.sub(r":([^:@/\s]+)@", r":***@", sanitized)
    # Enmascarar parámetros password=..., pwd=..., secret=... tanto con comillas como sin comillas
    sanitized = re.sub(
        r"""(['"]?(?:password|pwd|secret)['"]?\s*[:=]\s*['"]?)([^'"\s,;&]+)(['"]?)""",
        r"\1***\3",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


class SecureConnection(pg8000.dbapi.Connection):
    """
    Conexión PG8000 reforzada:
    - Implementa y valida channel_binding ('disable', 'prefer', 'require').
    - Exige SCRAM-SHA-256-PLUS si channel_binding=require.
    - Soporta los mensajes 11 (AuthenticationSASLContinue) y 12 (AuthenticationSASLFinal).
    - Valida que SCRAM-SHA-256-PLUS se haya completado antes de aceptar AuthenticationOk (código 0).
    - Impide degradación silenciosa de seguridad.
    """
    def __init__(self, *args, channel_binding_mode: str = "prefer", sslmode: Optional[str] = None, **kwargs):
        self._channel_binding_mode = channel_binding_mode
        self._sslmode = sslmode
        self._sasl_plus_completed = False
        super().__init__(*args, **kwargs)

    def handle_AUTHENTICATION_REQUEST(self, data, context):
        auth_code = i_unpack(data)[0]
        if self._channel_binding_mode == "disable":
            self.channel_binding = None
        elif self._channel_binding_mode == "require":
            if self.channel_binding is None:
                raise pg8000.exceptions.InterfaceError(
                    "channel_binding=require solicitado, pero la conexión no es SSL o no se pudo establecer channel binding."
                )
            if auth_code == 10:
                mechanisms = [m.decode("ascii") for m in data[4:-2].split(NULL_BYTE)]
                if not any(m.endswith("-PLUS") for m in mechanisms):
                    raise pg8000.exceptions.InterfaceError(
                        "channel_binding=require solicitado, pero el servidor no ofrece mecanismos SCRAM con channel binding (SCRAM-SHA-256-PLUS)."
                    )
            elif auth_code == 0:
                auth_obj = getattr(self, "auth", None)
                stage = getattr(auth_obj, "stage", None)
                stage_name = getattr(stage, "name", str(stage))
                is_completed = (
                    getattr(self, "_sasl_plus_completed", False)
                    or (
                        auth_obj is not None
                        and getattr(auth_obj, "mechanism_name", "").endswith("-PLUS")
                        and stage_name == "set_server_final"
                    )
                )
                if not is_completed:
                    raise pg8000.exceptions.InterfaceError(
                        "channel_binding=require solicitado, pero se recibió AuthenticationOk sin haber completado la autenticación SCRAM-SHA-256-PLUS."
                    )
            elif auth_code not in (11, 12):
                raise pg8000.exceptions.InterfaceError(
                    f"channel_binding=require solicitado, pero el servidor requiere autenticación no-SCRAM ({auth_code})."
                )
        super().handle_AUTHENTICATION_REQUEST(data, context)
        if self._channel_binding_mode == "require":
            if auth_code == 10:
                if hasattr(self, "auth") and self.auth and not getattr(self.auth, "mechanism_name", "").endswith("-PLUS"):
                    raise pg8000.exceptions.InterfaceError(
                        f"channel_binding=require solicitado, pero el mecanismo seleccionado no es -PLUS ({getattr(self.auth, 'mechanism_name', '')})."
                    )
            elif auth_code == 12:
                if hasattr(self, "auth") and self.auth and getattr(self.auth, "mechanism_name", "").endswith("-PLUS"):
                    self._sasl_plus_completed = True


def secure_pg8000_connect(*args, channel_binding: str = "prefer", sslmode: Optional[str] = None, **kwargs):
    """
    Envoltorio seguro para pg8000.dbapi.connect:
    - Respeta sslmode=disable, allow, prefer, require, verify-ca, verify-full.
    - Aplica fallback en prefer y allow respetando channel_binding.
    - Respeta channel_binding=disable, prefer, require sin degradar requerimientos.
    - Enmascara credenciales y suprime trazas encadenadas en todas las excepciones.
    """
    cb_mode = channel_binding
    sm_mode = sslmode or ("disable" if kwargs.get("ssl_context") is False else "require")

    pwd = kwargs.get("password")
    if not pwd and len(args) > 4:
        pwd = args[4]
    if isinstance(pwd, bytes):
        pwd = pwd.decode("utf-8", errors="ignore")

    def _safe_raise(exc: Exception):
        safe_msg = sanitize_error_message(str(exc), pwd)
        try:
            raise type(exc)(safe_msg) from None
        except TypeError:
            raise RuntimeError(safe_msg) from None

    if sm_mode == "disable":
        kwargs["ssl_context"] = False
        try:
            return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="disable", **kwargs)
        except Exception as e:
            _safe_raise(e)

    elif sm_mode == "prefer":
        ssl_ctx = kwargs.get("ssl_context")
        if ssl_ctx is False:
            try:
                return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="prefer", **kwargs)
            except Exception as e:
                _safe_raise(e)
        try:
            return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="prefer", **kwargs)
        except (pg8000.exceptions.InterfaceError, ssl.SSLError, socket.error) as exc:
            err_text = str(exc)
            if "refuses SSL" in err_text or "not available" in err_text or "communication error" in err_text:
                if cb_mode == "require":
                    # No se puede hacer fallback a texto plano si channel_binding=require
                    _safe_raise(exc)
                logger.warning("[DB_ADAPTER] Servidor no soporta SSL en modo prefer; reintentando sin SSL...")
                fallback_kwargs = dict(kwargs)
                fallback_kwargs["ssl_context"] = False
                try:
                    return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="prefer", **fallback_kwargs)
                except Exception as fb_exc:
                    _safe_raise(fb_exc)
            _safe_raise(exc)
        except Exception as e:
            _safe_raise(e)

    elif sm_mode == "allow":
        # Intenta sin SSL primero preservando channel_binding_mode=cb_mode
        no_ssl_kwargs = dict(kwargs)
        no_ssl_kwargs["ssl_context"] = False
        try:
            return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="allow", **no_ssl_kwargs)
        except (pg8000.exceptions.InterfaceError, pg8000.exceptions.DatabaseError, socket.error) as exc:
            logger.warning("[DB_ADAPTER] Conexión sin SSL falló en modo allow; reintentando con SSL...")
            ctx = kwargs.get("ssl_context")
            if ctx is False or ctx is None:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_REQUIRED
            ssl_kwargs = dict(kwargs)
            ssl_kwargs["ssl_context"] = ctx
            try:
                return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode="allow", **ssl_kwargs)
            except Exception as ssl_exc:
                _safe_raise(ssl_exc)
        except Exception as e:
            _safe_raise(e)

    else:
        # require, verify-ca, verify-full
        try:
            return SecureConnection(*args, channel_binding_mode=cb_mode, sslmode=sm_mode, **kwargs)
        except Exception as e:
            _safe_raise(e)


# Reemplazar la fábrica por defecto de pg8000 para que cualquier llamada a connect use la versión segura
pg8000.dbapi.connect = secure_pg8000_connect


def prepare_postgres_engine_args(raw_url: Optional[str] = None) -> Tuple[Any, Dict[str, Any]]:
    """
    Parsea, valida y prepara la URL y los connect_args para SQLAlchemy con pg8000.
    - Soporta y valida estrictamente sslmode: disable, allow, prefer, require, verify-ca, verify-full.
    - Soporta y valida estrictamente channel_binding: disable, prefer, require.
    - Rechaza parámetros no soportados sin exponer credenciales en los mensajes ni en trazas de excepciones.
    - Elimina parámetros de query que no soporta pg8000 para evitar TypeErrors.
    """
    if not raw_url:
        raise ValueError("DATABASE_URL no puede estar vacía.") from None

    from sqlalchemy.engine import make_url
    try:
        u = make_url(raw_url)
    except Exception:
        raise ValueError("URL de base de datos malformada.") from None

    if u.drivername in ("postgres", "postgresql"):
        u = u.set(drivername="postgresql+pg8000")
    elif not u.drivername.startswith("postgresql"):
        raise ValueError("Protocolo de base de datos no soportado.") from None

    query = dict(u.query)
    connect_args: Dict[str, Any] = {}

    # 1. Validar channel_binding
    cb = query.pop("channel_binding", None)
    VALID_CB = ("disable", "prefer", "require")
    if cb is not None and cb not in VALID_CB:
        raise ValueError(f"Valor de channel_binding no válido: '{cb}'") from None
    connect_args["channel_binding"] = cb or "prefer"

    # 2. Validar sslmode y configurar ssl_context
    sslmode = query.pop("sslmode", None)
    VALID_SSLMODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
    if sslmode is not None and sslmode not in VALID_SSLMODES:
        raise ValueError(f"Valor de sslmode no válido: '{sslmode}'") from None

    if sslmode == "disable":
        connect_args["ssl_context"] = False
        connect_args["sslmode"] = "disable"
    elif sslmode in ("require", "verify-full"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl_context"] = ctx
        connect_args["sslmode"] = sslmode
    elif sslmode == "verify-ca":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl_context"] = ctx
        connect_args["sslmode"] = "verify-ca"
    elif sslmode == "prefer":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl_context"] = ctx
        connect_args["sslmode"] = "prefer"
    elif sslmode == "allow":
        connect_args["ssl_context"] = False
        connect_args["sslmode"] = "allow"
    else:
        # Si no se especifica y el host es remoto, exigir SSL por defecto
        if u.host not in ("localhost", "127.0.0.1", "::1", None):
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            connect_args["ssl_context"] = ctx
            connect_args["sslmode"] = "require"
        else:
            connect_args["sslmode"] = "prefer"

    # 3. Mapear parámetros soportados por pg8000
    if "connect_timeout" in query:
        val = query.pop("connect_timeout")
        try:
            connect_args["timeout"] = int(val)
        except (ValueError, TypeError):
            raise ValueError("Valor de connect_timeout inválido.") from None

    if "application_name" in query:
        connect_args["application_name"] = query.pop("application_name")

    # 4. Rechazar parámetros no reconocidos (sin exponer valores sensibles)
    if query:
        unsupported = sorted(query.keys())[0]
        raise ValueError(f"Parámetro de conexión no soportado: '{unsupported}'") from None

    clean_u = u.set(query={})
    return clean_u, connect_args


def make_connection_creator(clean_url, connect_args: Dict[str, Any]):
    """Crea una fábrica de conexiones para SQLAlchemy con validación de seguridad y fallback."""
    user = clean_url.username or "postgres"
    password = clean_url.password
    host = clean_url.host or "localhost"
    port = clean_url.port or 5432
    database = clean_url.database

    base_kwargs: Dict[str, Any] = {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
    }
    for k in ("timeout", "application_name", "ssl_context"):
        if k in connect_args:
            base_kwargs[k] = connect_args[k]

    cb = connect_args.get("channel_binding", "prefer")
    sm = connect_args.get("sslmode", "require")

    def creator():
        return secure_pg8000_connect(
            **base_kwargs,
            channel_binding=cb,
            sslmode=sm,
        )

    return creator


def get_database_url(hide_password: bool = False) -> Optional[str]:
    """Retorna la URL normalizada para SQLAlchemy con driver pg8000."""
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return None
    clean_u, _ = prepare_postgres_engine_args(raw)
    return clean_u.render_as_string(hide_password=hide_password)


def get_engine():
    """Retorna el motor singleton de SQLAlchemy para PostgreSQL."""
    global _ENGINE
    if _ENGINE is None and is_postgres():
        from sqlalchemy import create_engine
        raw = os.getenv("DATABASE_URL", "").strip()
        clean_url, connect_args = prepare_postgres_engine_args(raw)
        creator = make_connection_creator(clean_url, connect_args)
        try:
            _ENGINE = create_engine(
                clean_url,
                creator=creator,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10,
            )
            logger.info("[DB_ADAPTER] Motor PostgreSQL (pg8000) conectado exitosamente con SSL y channel_binding.")
        except Exception as e:
            safe_msg = sanitize_error_message(str(e))
            logger.error(f"[DB_ADAPTER] Error al conectar motor PostgreSQL: {safe_msg}")
            raise RuntimeError(f"Error de conexión a PostgreSQL: {safe_msg}") from None
    return _ENGINE


class RowProxy:
    """
    Simula la interfaz de sqlite3.Row sobre filas de SQLAlchemy o diccionarios.
    Permite acceso tanto por nombre de columna row['id'] como por índice row[0],
    así como dict(row) y row.keys().
    """
    def __init__(self, row: Any, columns: Optional[List[str]] = None):
        if hasattr(row, "_mapping"):
            self._mapping = dict(row._mapping)
            self._tuple = tuple(row)
        elif isinstance(row, dict):
            self._mapping = dict(row)
            self._tuple = tuple(row.values())
        else:
            self._tuple = tuple(row)
            if columns:
                self._mapping = {col: self._tuple[i] for i, col in enumerate(columns)}
            else:
                self._mapping = {str(i): val for i, val in enumerate(self._tuple)}

    def __getitem__(self, key: Union[str, int]) -> Any:
        if isinstance(key, int):
            return self._tuple[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping.items())

    def __len__(self):
        return len(self._tuple)

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()

    def items(self):
        return self._mapping.items()

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)

    def __repr__(self):
        return f"<RowProxy {self._mapping}>"


class CursorProxy:
    """
    Envuelve CursorResult de SQLAlchemy para exponer la interfaz DB-API de SQLite:
    fetchone(), fetchall(), rowcount, lastrowid.
    """
    def __init__(self, result: Any, last_id: Optional[int] = None):
        self._result = result
        self._rows = None
        self._last_id = last_id
        if result is not None and hasattr(result, "rowcount"):
            self.rowcount = result.rowcount
        else:
            self.rowcount = 0

    @property
    def lastrowid(self) -> Optional[int]:
        if self._last_id is not None:
            return self._last_id
        if self._result is not None:
            try:
                if hasattr(self._result, "inserted_primary_key") and self._result.inserted_primary_key:
                    return self._result.inserted_primary_key[0]
            except Exception:
                pass
        return None

    def fetchone(self) -> Optional[RowProxy]:
        if self._result is None:
            return None
        row = self._result.fetchone()
        if row is None:
            return None
        return RowProxy(row)

    def fetchall(self) -> List[RowProxy]:
        if self._result is None:
            return []
        rows = self._result.fetchall()
        return [RowProxy(r) for r in rows]

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


def _adapt_sql_for_postgres(sql: str, params: Optional[Union[tuple, list, dict]] = None) -> Tuple[str, Dict[str, Any], bool]:
    """
    Adapta consultas SQL escritas para SQLite a PostgreSQL:
    1. Ignora PRAGMAs y comandos de bloqueo SQLite (BEGIN IMMEDIATE).
    2. Convierte INSERT OR IGNORE a INSERT ... ON CONFLICT DO NOTHING.
    3. Convierte parámetros posicionales '?' a parámetros con nombre ':p_0', ':p_1', ...
    4. Agrega 'RETURNING id' en inserciones de interactions si no está presente.
    """
    clean_sql = sql.strip()

    # Operaciones no aplicables a Postgres
    if clean_sql.upper().startswith("PRAGMA") or clean_sql.upper() == "BEGIN IMMEDIATE":
        return "", {}, False

    # Idempotencia de interacciones
    if "INSERT OR IGNORE INTO interactions" in clean_sql:
        clean_sql = clean_sql.replace(
            "INSERT OR IGNORE INTO interactions",
            "INSERT INTO interactions"
        )
        if "ON CONFLICT" not in clean_sql.upper():
            clean_sql += " ON CONFLICT (client_message_id) WHERE client_message_id IS NOT NULL DO NOTHING"

    # En Postgres necesitamos RETURNING id para emular cursor.lastrowid
    is_interaction_insert = "INSERT INTO interactions" in clean_sql and "RETURNING" not in clean_sql.upper()
    if is_interaction_insert:
        clean_sql += " RETURNING id"

    # Traducción de funciones de fecha SQLite para compatibilidad con PostgreSQL
    if "STRFTIME" in clean_sql.upper():
        # Caso combinado STRFTIME('%H', DATETIME(col, 'interval'))
        clean_sql = re.sub(
            r"STRFTIME\s*\(\s*'%H'\s*,\s*DATETIME\s*\(\s*([a-zA-Z0-9_\.]+)\s*,\s*['\"]([+-]?\d+\s+\w+)['\"]\s*\)\s*\)",
            r"EXTRACT(HOUR FROM (CAST(\1 AS TIMESTAMP) + INTERVAL '\2'))",
            clean_sql,
            flags=re.IGNORECASE,
        )
        # STRFTIME('%s', col) -> epoch en segundos
        clean_sql = re.sub(
            r"STRFTIME\s*\(\s*'%s'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)",
            r"EXTRACT(EPOCH FROM CAST(\1 AS TIMESTAMP))",
            clean_sql,
            flags=re.IGNORECASE,
        )
        # STRFTIME('%H', col) -> hora numérica
        clean_sql = re.sub(
            r"STRFTIME\s*\(\s*'%H'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)",
            r"EXTRACT(HOUR FROM CAST(\1 AS TIMESTAMP))",
            clean_sql,
            flags=re.IGNORECASE,
        )
        # STRFTIME('%Y-%m-%d', col) -> fecha formato YYYY-MM-DD
        clean_sql = re.sub(
            r"STRFTIME\s*\(\s*'%Y-%m-%d'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)",
            r"TO_CHAR(CAST(\1 AS TIMESTAMP), 'YYYY-MM-DD')",
            clean_sql,
            flags=re.IGNORECASE,
        )

    # Convertir parámetros '?' a ':p_0', ':p_1', ...
    bound_params = {}
    if params is not None:
        if isinstance(params, (tuple, list)):
            parts = clean_sql.split("?")
            if len(parts) - 1 == len(params):
                reconstructed = []
                for i, part in enumerate(parts[:-1]):
                    reconstructed.append(part)
                    p_name = f"p_{i}"
                    reconstructed.append(f":{p_name}")
                    bound_params[p_name] = params[i]
                reconstructed.append(parts[-1])
                clean_sql = "".join(reconstructed)
            else:
                clean_sql = clean_sql
        elif isinstance(params, dict):
            bound_params = params

    return clean_sql, bound_params, is_interaction_insert


class PostgresConnectionWrapper:
    """
    Envuelve una conexión SQLAlchemy a PostgreSQL para presentar la misma interfaz
    que sqlite3.Connection.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._trans = None

    def execute(self, sql: str, params: Optional[Union[tuple, list, dict]] = None) -> CursorProxy:
        from sqlalchemy import text
        adapted_sql, bound_params, is_insert = _adapt_sql_for_postgres(sql, params)
        if not adapted_sql:
            # Comando omitido (ej. PRAGMA)
            return CursorProxy(None)

        result = self._conn.execute(text(adapted_sql), bound_params)
        last_id = None
        if is_insert:
            row = result.fetchone()
            if row is not None:
                last_id = row[0]
            cursor = CursorProxy(result, last_id=last_id)
            # RETURNING es la evidencia de inserción, independientemente del driver.
            cursor.rowcount = 1 if row is not None else 0
            return cursor
        return CursorProxy(result)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()


def ensure_postgres_schema():
    """Crea todas las tablas requeridas en PostgreSQL si no existen."""
    global _PG_INITIALIZED
    if _PG_INITIALIZED or not is_postgres():
        return

    engine = get_engine()
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(WEBHOOK_RECEIPTS_SCHEMA))
        from conversation_memory import SCHEMA as memory_schema
        conn.execute(text(memory_schema))
        # 1. Tabla de interacciones
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS interactions (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'test',
                detected_language TEXT DEFAULT 'es',
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                resolved_autonomously INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL NOT NULL DEFAULT 0.0,
                escalated_to_human INTEGER NOT NULL DEFAULT 0,
                is_predefined_response INTEGER NOT NULL DEFAULT 0,
                interaction_type TEXT NOT NULL DEFAULT 'llm',
                is_rate_limit INTEGER NOT NULL DEFAULT 0,
                client_message_id TEXT
            );
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_client_message_id
            ON interactions(client_message_id)
            WHERE client_message_id IS NOT NULL;
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp);
        """))

        # 2. Deduplicación de webhooks
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS processed_webhooks (
                message_id TEXT PRIMARY KEY,
                user_id TEXT,
                received_at TEXT NOT NULL
            );
        """))

        # 3. Solicitudes a asesores (handoffs)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                question TEXT NOT NULL,
                context TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                advisor TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            );
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_request
            ON requests(channel, user_id)
            WHERE status != 'closed';
        """))

        # 4. Métricas operativas
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS operational_events (
                id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                generation_ms REAL,
                response_attempt_ms REAL,
                route TEXT,
                model_claims_resolved INTEGER NOT NULL DEFAULT 0,
                provider_rate_limit INTEGER NOT NULL DEFAULT 0,
                handoff_id TEXT
            );
        """))

        # 5. Catálogo dinámico de tours y assets multimedia
        conn.execute(text("""
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
        """))
    _PG_INITIALIZED = True
    logger.info("[DB_ADAPTER] Esquema PostgreSQL verificado e inicializado.")


@contextmanager
def get_db_session(sqlite_path: str = "texeira_logs.db"):
    """
    Context manager universal:
    - Si DATABASE_URL está definida: provee una sesión PostgreSQL con auto-commit/rollback.
    - Si no: provee una conexión SQLite nativa con row_factory.
    """
    if is_postgres():
        ensure_postgres_schema()
        engine = get_engine()
        raw_conn = engine.connect()
        wrapper = PostgresConnectionWrapper(raw_conn)
        try:
            yield wrapper
            wrapper.commit()
        except Exception:
            wrapper.rollback()
            raise
        finally:
            wrapper.close()
    else:
        conn = sqlite3.connect(sqlite_path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()
