"""
db_adapter.py — Capa de persistencia universal (PostgreSQL vía DATABASE_URL o SQLite local).

Permite que el sistema opere con costo $0.00 en Cloud Run utilizando una base de datos
PostgreSQL remota (Supabase, Neon, Cloud SQL) para no perder datos en scale-to-zero,
manteniendo 100% de compatibilidad local con SQLite para pruebas y desarrollo.
"""

import os
import re
import sqlite3
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

_ENGINE = None
_PG_INITIALIZED = False


def is_postgres() -> bool:
    """Retorna True si DATABASE_URL está configurada para PostgreSQL."""
    url = os.getenv("DATABASE_URL", "").strip()
    return bool(url and (url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+")))


def get_database_url() -> Optional[str]:
    """Retorna la URL normalizada para SQLAlchemy con driver pg8000."""
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return None
    if raw.startswith("postgres://"):
        raw = "postgresql+pg8000://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+pg8000://" + raw[len("postgresql://"):]
    return raw


def get_engine():
    """Retorna el motor singleton de SQLAlchemy para PostgreSQL."""
    global _ENGINE
    if _ENGINE is None and is_postgres():
        from sqlalchemy import create_engine
        url = get_database_url()
        try:
            _ENGINE = create_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10,
            )
            logger.info("[DB_ADAPTER] Motor PostgreSQL (pg8000) conectado exitosamente.")
        except Exception as e:
            logger.error(f"[DB_ADAPTER] Error al conectar motor PostgreSQL: {e}")
            raise
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
            clean_sql += " ON CONFLICT (client_message_id) DO NOTHING"

    # En Postgres necesitamos RETURNING id para emular cursor.lastrowid
    is_interaction_insert = "INSERT INTO interactions" in clean_sql and "RETURNING" not in clean_sql.upper()
    if is_interaction_insert:
        clean_sql += " RETURNING id"

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
            try:
                row = result.fetchone()
                if row:
                    last_id = row[0]
            except Exception:
                pass
        return CursorProxy(result, last_id=last_id)

    def commit(self) -> None:
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self) -> None:
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def ensure_postgres_schema():
    """Crea todas las tablas requeridas en PostgreSQL si no existen."""
    global _PG_INITIALIZED
    if _PG_INITIALIZED or not is_postgres():
        return

    engine = get_engine()
    from sqlalchemy import text
    with engine.begin() as conn:
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
