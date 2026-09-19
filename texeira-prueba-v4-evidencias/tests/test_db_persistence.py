"""
test_db_persistence.py — Pruebas unitarias de persistencia universal (SQLite y PostgreSQL).
"""

import os
import sys
import tempfile
from pathlib import Path

# Agregar directorio raíz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db_adapter
import database
import handoff_support
import operational_metrics


def test_db_adapter_utilities():
    print("--- Probando utilidades de db_adapter ---")
    # 1. Detección de PostgreSQL
    orig = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = "postgres://usr:pwd@host:5432/db"
        assert db_adapter.is_postgres() is True
        assert db_adapter.get_database_url() == "postgresql+pg8000://usr:pwd@host:5432/db"

        os.environ["DATABASE_URL"] = "postgresql://usr:pwd@host:5432/db"
        assert db_adapter.is_postgres() is True
        assert db_adapter.get_database_url() == "postgresql+pg8000://usr:pwd@host:5432/db"

        os.environ["DATABASE_URL"] = ""
        assert db_adapter.is_postgres() is False
        assert db_adapter.get_database_url() is None
    finally:
        if orig is not None:
            os.environ["DATABASE_URL"] = orig
        else:
            os.environ.pop("DATABASE_URL", None)

    # 2. Adaptación de SQL para Postgres
    sql_pragma = "PRAGMA journal_mode=WAL"
    adapted, binds, _ = db_adapter._adapt_sql_for_postgres(sql_pragma)
    assert adapted == ""

    sql_begin = "BEGIN IMMEDIATE"
    adapted, binds, _ = db_adapter._adapt_sql_for_postgres(sql_begin)
    assert adapted == ""

    sql_ignore = "INSERT OR IGNORE INTO interactions (user_id, client_message_id) VALUES (?, ?)"
    adapted, binds, is_insert = db_adapter._adapt_sql_for_postgres(sql_ignore, ("user1", "msg123"))
    assert "ON CONFLICT (client_message_id) DO NOTHING" in adapted
    assert ":p_0" in adapted and ":p_1" in adapted
    assert binds == {"p_0": "user1", "p_1": "msg123"}
    assert is_insert is True

    # 3. RowProxy
    mock_dict = {"id": 42, "user_id": "51999999999", "status": "pending"}
    row = db_adapter.RowProxy(mock_dict)
    assert row["id"] == 42
    assert row[0] == 42
    assert row["user_id"] == "51999999999"
    assert dict(row) == mock_dict
    assert len(row) == 3
    print("  PASS | Utilidades db_adapter OK")


def test_database_sqlite_flow():
    print("--- Probando flujo database.py con SQLite ---")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db = f.name

    try:
        database.init_db(temp_db)

        # Inserción normal
        id1 = database.log_interaction(
            user_id="turista-1",
            channel="whatsapp",
            detected_language="es",
            user_message="Hola, precios de tours",
            bot_response="Texeira Travel ofrece tours en Cusco...",
            resolved_autonomously=True,
            latency_ms=120.5,
            escalated_to_human=False,
            db_path=temp_db,
        )
        assert id1 > 0

        # Inserción con client_message_id (idempotencia)
        id2 = database.log_interaction(
            user_id="turista-2",
            channel="whatsapp",
            detected_language="es",
            user_message="Información Machu Picchu",
            bot_response="Información detallada...",
            resolved_autonomously=True,
            latency_ms=95.0,
            escalated_to_human=False,
            client_message_id="msg-uuid-abc",
            db_path=temp_db,
        )
        assert id2 > 0

        # Reintento con el mismo client_message_id no debe crear nueva fila
        id2_retry = database.log_interaction(
            user_id="turista-2",
            channel="whatsapp",
            detected_language="es",
            user_message="Información Machu Picchu",
            bot_response="Información detallada actualizada...",
            resolved_autonomously=True,
            latency_ms=90.0,
            escalated_to_human=False,
            client_message_id="msg-uuid-abc",
            db_path=temp_db,
        )
        assert id2_retry == id2

        # Deduplicación de webhooks
        assert database.is_duplicate_webhook("wamid.12345", "turista-1", db_path=temp_db) is False
        assert database.is_duplicate_webhook("wamid.12345", "turista-1", db_path=temp_db) is True

        # Resumen de métricas
        summary = database.get_metrics_summary(temp_db)
        assert summary["total_interactions"] >= 2
        assert summary["resolution_rate_pct"] == 100.0
        assert "after_hours_count" in summary
        print("  PASS | Flujo database.py SQLite OK")
    finally:
        if database._connection:
            try:
                database._connection.close()
            except Exception:
                pass
            database._connection = None
        if os.path.exists(temp_db):
            try:
                os.unlink(temp_db)
            except Exception:
                pass


def test_handoff_and_operational_metrics_sqlite():
    print("--- Probando handoff y operational_metrics con SQLite ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        handoff_support.DB = Path(tmpdir) / "requests.db"
        operational_metrics.DB = Path(tmpdir) / "operational.db"

        # Handoff: creación y actualización
        req, created = handoff_support.create_request(
            user_id="user-support-1",
            channel="whatsapp",
            question="Quiero hablar con un asesor",
            context=[{"role": "user", "content": "Quiero asesor"}],
        )
        assert created is True
        assert req["status"] == "pending"
        ticket = req["id"]

        # Reintento idéntico no debe duplicar solicitud abierta
        req2, created2 = handoff_support.create_request(
            user_id="user-support-1",
            channel="whatsapp",
            question="Quiero hablar con un asesor",
            context=[],
        )
        assert created2 is False
        assert req2["id"] == ticket

        # Transición de estado
        handoff_support.update_request(ticket, "in_progress", "Carlos Asesor", "")
        handoff_support.update_request(ticket, "closed", "Carlos Asesor", "Cliente atendido con éxito.")

        # Métricas operativas
        evt_id = operational_metrics.start()
        assert evt_id is not None
        operational_metrics.finish(
            evt_id,
            status="api_accepted",
            generation_ms=150.0,
            response_attempt_ms=25.0,
            result={"response_route": "social", "resolved_autonomously": True},
        )
        op_summary = operational_metrics.summary()
        assert op_summary["received"] >= 1
        assert op_summary["api_accepted"] >= 1
        print("  PASS | Flujo handoff y operational_metrics SQLite OK")


def test_postgres_wrapper_translation():
    print("--- Probando adaptador y ejecución con PostgresConnectionWrapper ---")
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as raw_conn:
        wrapper = db_adapter.PostgresConnectionWrapper(raw_conn)
        wrapper.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, msg TEXT, user_id TEXT)")
        # Inserción con parámetros posicionales '?'
        wrapper.execute("INSERT INTO test_table (id, msg, user_id) VALUES (?, ?, ?)", (1, "Hola Texeira", "51999999999"))
        # Consulta
        res = wrapper.execute("SELECT * FROM test_table WHERE id = ?", (1,))
        row = res.fetchone()
        assert row is not None
        assert row["msg"] == "Hola Texeira"
        assert row["user_id"] == "51999999999"
        assert row[0] == 1
        assert dict(row) == {"id": 1, "msg": "Hola Texeira", "user_id": "51999999999"}
        # Fetchall
        rows = wrapper.execute("SELECT * FROM test_table").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == 1
    print("  PASS | PostgresConnectionWrapper OK")


if __name__ == "__main__":
    test_db_adapter_utilities()
    test_database_sqlite_flow()
    test_handoff_and_operational_metrics_sqlite()
    test_postgres_wrapper_translation()
    print("\n============================================================")
    print("TODAS LAS PRUEBAS DE PERSISTENCIA UNIVERSAL PASARON CON ÉXITO")
    print("============================================================")
