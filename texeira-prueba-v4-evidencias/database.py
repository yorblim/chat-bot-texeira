"""
database.py — Capa de persistencia para métricas de interacciones.

Este módulo es CENTRAL para la investigación: almacena cada interacción
turista-bot en SQLite y permite extraer métricas cuantitativas:
  - Tasa de resolución autónoma (% de consultas resueltas sin fallback)
  - Latencia operativa promedio (ms entre mensaje y respuesta)
  - Tasa de escalamiento a humano
  - Volumen total de interacciones

Estas métricas sustentan el pretest/postest de la tesis.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from db_adapter import (
    is_postgres,
    ensure_postgres_schema,
    get_engine,
    PostgresConnectionWrapper,
)

# Variable global para la conexión SQLite
_connection: Optional[sqlite3.Connection] = None


def _get_connection(db_path: str = "texeira_logs.db"):
    """
    Retorna la conexión a la base de datos:
    - Si DATABASE_URL está configurada, utiliza PostgreSQL vía SQLAlchemy (pg8000).
    - Si no, retorna una conexión singleton a SQLite local.
    """
    if is_postgres():
        ensure_postgres_schema()
        return PostgresConnectionWrapper(get_engine().connect())

    global _connection
    if _connection is None:
        _connection = sqlite3.connect(db_path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")  # Mejor concurrencia
    return _connection


def init_db(db_path: str = "texeira_logs.db") -> None:
    """
    Inicializa las tablas en PostgreSQL o SQLite.

    Cada registro representa una interacción completa turista-bot y contiene
    los campos necesarios para calcular las métricas de la investigación:
      - resolved_autonomously: indicador clave de la hipótesis
      - latency_ms: indicador de rendimiento operativo
      - escalated_to_human: indicador de carga al personal
    """
    if is_postgres():
        ensure_postgres_schema()
        print("[DB] Base de datos PostgreSQL inicializada exitosamente.")
        return
    conn = _get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'test',
            detected_language TEXT DEFAULT 'es',
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            resolved_autonomously INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL NOT NULL DEFAULT 0.0,
            escalated_to_human INTEGER NOT NULL DEFAULT 0,
            is_predefined_response INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Migración para bases de datos creadas antes de agregar la columna
    # is_predefined_response (auditoría #4): si la columna no existe, se agrega.
    columns = [row[1] for row in conn.execute("PRAGMA table_info(interactions)").fetchall()]
    if "is_predefined_response" not in columns:
        conn.execute("ALTER TABLE interactions ADD COLUMN is_predefined_response INTEGER NOT NULL DEFAULT 0")

    # Migración auditoría #2: interaction_type separa los tipos de interacción
    # en la base de datos para que las métricas de investigación no se
    # contaminen con navegación de UI:
    #   - 'llm'           → cadena RAG completa (conversación real)
    #   - 'predefined'    → respuesta enlatada por palabra clave
    #   - 'ui_navigation' → acciones de UI (ej. "Ver más opciones"), no son
    #                       éxito ni fallo del RAG
    if "interaction_type" not in columns:
        conn.execute("ALTER TABLE interactions ADD COLUMN interaction_type TEXT NOT NULL DEFAULT 'llm'")
        # Las filas históricas que eran predefinidas se reclasifican
        conn.execute(
            "UPDATE interactions SET interaction_type = 'predefined' "
            "WHERE is_predefined_response = 1"
        )

    # Migración auditoría #5: is_rate_limit separa errores de infraestructura
    # (rate-limit 429 del proveedor LLM) de fallbacks reales del RAG.
    # Un rate-limit NO es una consulta sin respuesta — es una falla del proveedor.
    if "is_rate_limit" not in columns:
        conn.execute("ALTER TABLE interactions ADD COLUMN is_rate_limit INTEGER NOT NULL DEFAULT 0")

    # Migración auditoría #3: client_message_id permite idempotencia en
    # reintentos (el mismo mensaje reintentado no duplica filas).
    # Índice único parcial: solo se aplica a filas que SÍ tienen el id.
    if "client_message_id" not in columns:
        conn.execute("ALTER TABLE interactions ADD COLUMN client_message_id TEXT")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_client_message_id
        ON interactions(client_message_id)
        WHERE client_message_id IS NOT NULL
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp)
    """)

    # Tabla de deduplicacion de webhooks WhatsApp.
    # Registra message_id ANTES de procesar para evitar duplicados.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_webhooks (
            message_id TEXT PRIMARY KEY,
            user_id TEXT,
            received_at TEXT NOT NULL
        )
    """)
    conn.commit()
    print(f"[DB] Base de datos inicializada en: {db_path}")


def log_interaction(
    user_id: str,
    channel: str,
    detected_language: str,
    user_message: str,
    bot_response: str,
    resolved_autonomously: bool,
    latency_ms: float,
    escalated_to_human: bool,
    is_predefined_response: bool = False,
    interaction_type: str = "llm",
    is_rate_limit: bool = False,
    client_message_id: Optional[str] = None,
    db_path: str = "texeira_logs.db",
) -> int:
    """
    Registra una interacción completa en la tabla 'interactions'.

    Parámetros:
        user_id: Identificador del usuario (número de WhatsApp, ID de Messenger)
        channel: Canal de origen (whatsapp / messenger / test)
        detected_language: Idioma detectado en el mensaje del turista
        user_message: Texto exacto del mensaje entrante
        bot_response: Respuesta generada por el agente RAG
        resolved_autonomously: True si el bot respondió con contexto relevante,
                              False si cayó en el fallback (no dispongo de esa info)
        latency_ms: Tiempo en milisegundos entre recepción y respuesta
        escalated_to_human: True si se marcó para revisión humana
        is_predefined_response: True si la respuesta vino de botones/palabras
                                predefinidas (no pasó por el LLM)
        interaction_type: 'llm' | 'predefined' | 'ui_navigation'
        is_rate_limit: True si la interacción falló por rate-limit (429) del
                       proveedor LLM. Estas filas se excluyen de las métricas
                       de resolución autónoma porque son errores de infraestructura,
                       no fallos del RAG.
        client_message_id: UUID generado por el frontend por mensaje lógico.
                          Permite idempotencia: un reintento con el mismo id
                          NO crea una segunda fila, solo actualiza la existente.
        db_path: Ruta al archivo SQLite

    Retorna:
        ID del registro insertado (o actualizado)
    """
    conn = _get_connection(db_path)

    values = (
        datetime.now().isoformat(),
        user_id,
        channel,
        detected_language,
        user_message,
        bot_response,
        1 if resolved_autonomously else 0,
        latency_ms,
        1 if escalated_to_human else 0,
        1 if is_predefined_response else 0,
        interaction_type,
        1 if is_rate_limit else 0,
        client_message_id,
    )

    if client_message_id:
        # Idempotencia de reintentos: si ya existe una fila con este id
        # (ej. el primer intento falló solo del lado del cliente), se
        # actualiza la fila existente en lugar de duplicarla.
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO interactions
                (timestamp, user_id, channel, detected_language,
                 user_message, bot_response, resolved_autonomously,
                 latency_ms, escalated_to_human, is_predefined_response,
                 interaction_type, is_rate_limit, client_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        if cursor.rowcount == 0:
            conn.execute(
                """
                UPDATE interactions
                SET timestamp = ?, user_id = ?, channel = ?,
                    detected_language = ?, user_message = ?, bot_response = ?,
                    resolved_autonomously = ?, latency_ms = ?,
                    escalated_to_human = ?, is_predefined_response = ?,
                    interaction_type = ?, is_rate_limit = ?
                WHERE client_message_id = ?
                """,
                values[:-1] + (client_message_id,),
            )
            existing = conn.execute(
                "SELECT id FROM interactions WHERE client_message_id = ?",
                (client_message_id,),
            ).fetchone()
            conn.commit()
            return existing["id"] if existing else 0
        conn.commit()
        return cursor.lastrowid

    cursor = conn.execute(
        """
        INSERT INTO interactions
            (timestamp, user_id, channel, detected_language,
             user_message, bot_response, resolved_autonomously,
             latency_ms, escalated_to_human, is_predefined_response,
             interaction_type, is_rate_limit, client_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    conn.commit()
    return cursor.lastrowid


def get_metrics_summary(db_path: str = "texeira_logs.db") -> dict:
    """
    Calcula y retorna un resumen de métricas de todas las interacciones.

    Este es el endpoint que alimenta la evaluación cuantitativa del
    pretest/postest de la tesis.

    CORRECCIÓN DE AUDITORÍA #4: las métricas se reportan en bloques separados
    según interaction_type para evitar contaminación:
      - "conversacion_real_llm": interaction_type = 'llm' (cadena RAG completa)
      - "respuestas_predefinidas": interaction_type = 'predefined'
      - "ui_navigation": interacciones de navegación de UI (ej. "Ver más
        opciones") — NO cuentan como éxito ni fallo del RAG
      - "errores_infraestructura": is_rate_limit = 1 — errores 429 del proveedor
        LLM, excluidos de resolved_autonomously y escalation_rate

    CORRECCIÓN DE AUDITORÍA #5: las filas con is_rate_limit=1 se excluyen de
    TODAS las métricas de calidad (resolved_autonomously, escalation_rate,
    avg_latency) porque son fallas de infraestructura del proveedor, no del RAG.

    Las claves de nivel superior (total, avg_latency_ms, resolution_rate_pct,
    escalation_rate_pct) se calculan SOLO sobre conversación real + predefinidas
    EXCLUYENDO ui_navigation Y is_rate_limit.

    Retorna:
        Diccionario con las métricas calculadas
    """
    conn = _get_connection(db_path)

    def _compute_block(where_clause: str) -> dict:
        """Calcula total, latencia promedio, % resolución y % escalamiento
        para un subconjunto de interacciones definido por where_clause."""
        # Se excluyen filas con is_rate_limit de todos los bloques
        full_clause = f"({where_clause}) AND is_rate_limit = 0"
        total = conn.execute(
            f"SELECT COUNT(*) FROM interactions WHERE {full_clause}"
        ).fetchone()[0]

        if total == 0:
            return {
                "total_interactions": 0,
                "avg_latency_ms": 0.0,
                "resolution_rate_pct": 0.0,
                "escalation_rate_pct": 0.0,
            }

        avg_latency = conn.execute(
            f"SELECT AVG(latency_ms) FROM interactions WHERE {full_clause}"
        ).fetchone()[0] or 0.0

        resolved_count = conn.execute(
            f"SELECT COUNT(*) FROM interactions WHERE {full_clause} AND resolved_autonomously = 1"
        ).fetchone()[0]

        escalated_count = conn.execute(
            f"SELECT COUNT(*) FROM interactions WHERE {full_clause} AND escalated_to_human = 1"
        ).fetchone()[0]

        return {
            "total_interactions": total,
            "avg_latency_ms": round(avg_latency, 2),
            "resolution_rate_pct": round((resolved_count / total) * 100, 2),
            "escalation_rate_pct": round((escalated_count / total) * 100, 2),
        }

    # Bloque 1: conversación real (cadena RAG + LLM)
    llm_block = _compute_block("interaction_type = 'llm'")

    # Bloque 2: respuestas predefinidas (palabras clave exactas)
    predefined_block = _compute_block("interaction_type = 'predefined'")

    # Bloque 3: navegación de UI (no es éxito ni fallo del RAG)
    ui_block = _compute_block("interaction_type = 'ui_navigation'")

    # Bloque 4: errores de infraestructura (rate-limit 429 del proveedor LLM)
    rl_total = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE is_rate_limit = 1"
    ).fetchone()[0]
    rl_avg_latency = conn.execute(
        "SELECT AVG(latency_ms) FROM interactions WHERE is_rate_limit = 1"
    ).fetchone()[0] or 0.0
    rate_limit_block = {
        "total_interactions": rl_total,
        "avg_latency_ms": round(rl_avg_latency, 2),
    }

    # Métricas globales sobre interacciones conversacionales (llm + predefined),
    # EXCLUYENDO ui_navigation Y is_rate_limit para no contaminar la tasa
    # de resolución con artefactos de UI ni con errores de infraestructura.
    conversational_total = llm_block["total_interactions"] + predefined_block["total_interactions"]
    if conversational_total == 0:
        avg_latency = 0.0
        resolution_rate = 0.0
        escalation_rate = 0.0
        after_hours_count = 0
        after_hours_pct = 0.0
    else:
        avg_latency = conn.execute(
            "SELECT AVG(latency_ms) FROM interactions "
            "WHERE interaction_type != 'ui_navigation' AND is_rate_limit = 0"
        ).fetchone()[0] or 0.0
        resolved_total = conn.execute(
            "SELECT COUNT(*) FROM interactions "
            "WHERE interaction_type != 'ui_navigation' AND is_rate_limit = 0 "
            "AND resolved_autonomously = 1"
        ).fetchone()[0]
        escalated_total = conn.execute(
            "SELECT COUNT(*) FROM interactions "
            "WHERE interaction_type != 'ui_navigation' AND is_rate_limit = 0 "
            "AND escalated_to_human = 1"
        ).fetchone()[0]

        # Indicador 1.2 (Anexo 8 y 9): Tráfico atendido fuera del horario laboral estándar (18:00 a 08:00 hrs)
        after_hours_total = conn.execute(
            "SELECT COUNT(*) FROM interactions "
            "WHERE interaction_type != 'ui_navigation' AND is_rate_limit = 0 "
            "AND (CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) >= 18 OR CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) < 8)"
        ).fetchone()[0]

        resolution_rate = (resolved_total / conversational_total) * 100
        escalation_rate = (escalated_total / conversational_total) * 100
        after_hours_count = after_hours_total
        after_hours_pct = (after_hours_total / conversational_total) * 100

    return {
        "total_interactions": conversational_total,
        "avg_latency_ms": round(avg_latency, 2),
        "resolution_rate_pct": round(resolution_rate, 2),
        "escalation_rate_pct": round(escalation_rate, 2),
        "after_hours_count": after_hours_count,
        "after_hours_pct": round(after_hours_pct, 2),
        "conversacion_real_llm": llm_block,
        "respuestas_predefinidas": predefined_block,
        "ui_navigation": ui_block,
        "errores_infraestructura": rate_limit_block,
    }


def get_recent_interactions(limit: int = 20, db_path: str = "texeira_logs.db") -> list[dict]:
    """
    Recupera las últimas N interacciones registradas.
    Usado por el panel de administración (/dashboard).

    Retorna:
        Lista de diccionarios con los datos de cada interacción
    """
    conn = _get_connection(db_path)
    rows = conn.execute(
        """
        SELECT id, timestamp, user_id, channel, detected_language,
               user_message, bot_response, resolved_autonomously,
               latency_ms, escalated_to_human
        FROM interactions
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return [dict(row) for row in rows]


def is_duplicate_webhook(message_id: str, user_id: str = "", db_path: str = "texeira_logs.db") -> bool:
    """
    Verifica si un message_id ya fue procesado.
    Usa INSERT atomico: si el message_id no existia, lo registra y retorna False.
    Si ya existia, retorna True (duplicado).
    """
    if not message_id:
        return False
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO processed_webhooks (message_id, user_id, received_at) VALUES (?, ?, ?)",
            (message_id, user_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        # changes() == 1 significa que se inserto una fila nueva
        return cursor.rowcount == 0
    except (sqlite3.IntegrityError, Exception):
        # Violacion de PRIMARY KEY = message_id ya existia
        return True
