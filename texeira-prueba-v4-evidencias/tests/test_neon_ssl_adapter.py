"""
test_neon_ssl_adapter.py — Pruebas unitarias de conexión segura, validación SSL y manejo estricto de parámetros para Neon PostgreSQL.
"""

import os
import ssl
import sys
from pathlib import Path

# Agregar raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_adapter import (
    is_postgres,
    prepare_postgres_engine_args,
    get_database_url,
    get_engine,
    _ENGINE,
)
import db_adapter


def test_neon_url_ssl_require():
    """Valida que una URL típica de Neon con sslmode=require configure ssl_context con verificación de host."""
    raw_url = "postgresql://myuser:super_secret_pwd@ep-cool-123.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=disable"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert "super_secret_pwd" not in str(clean_url)
    assert clean_url.drivername == "postgresql+pg8000"
    assert clean_url.host == "ep-cool-123.us-east-2.aws.neon.tech"
    assert clean_url.database == "neondb"
    assert clean_url.query == {}  # Los parámetros no soportados por pg8000 fueron eliminados de la query

    # SSL Context debe exigir certificado y verificar hostname
    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    print("  PASS | test_neon_url_ssl_require")


def test_neon_url_ssl_verify_full():
    """Valida que sslmode=verify-full active verificación de CA y hostname."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=verify-full"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    print("  PASS | test_neon_url_ssl_verify_full")


def test_neon_url_ssl_verify_ca():
    """Valida que sslmode=verify-ca verifique CA sin comprobar hostname."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=verify-ca"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    print("  PASS | test_neon_url_ssl_verify_ca")


def test_neon_url_ssl_disable():
    """Valida que sslmode=disable no inyecte ssl_context."""
    raw_url = "postgresql://myuser:pwd@localhost:5432/neondb?sslmode=disable"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert "ssl_context" not in connect_args
    print("  PASS | test_neon_url_ssl_disable")


def test_channel_binding_require_explicitly_rejected():
    """Valida que channel_binding=require sea rechazado explícitamente sin filtrar credenciales."""
    sensitive_pass = "top_secret_token_abc999"
    raw_url = f"postgresql://myuser:{sensitive_pass}@ep-cool.neon.tech/neondb?sslmode=require&channel_binding=require"

    try:
        prepare_postgres_engine_args(raw_url)
        assert False, "Debería haber lanzado ValueError ante channel_binding=require"
    except ValueError as exc:
        err_msg = str(exc)
        assert "channel_binding=require no es soportado por el controlador pg8000" in err_msg
        assert sensitive_pass not in err_msg, "Las credenciales no deben exponerse en el mensaje de error"
    print("  PASS | test_channel_binding_require_explicitly_rejected")


def test_unsupported_parameters_rejected():
    """Valida que cualquier parámetro no soportado sea rechazado de forma segura."""
    sensitive_pass = "my_private_pass_xyz123"
    raw_url = f"postgresql://myuser:{sensitive_pass}@ep-cool.neon.tech/neondb?sslmode=require&invalid_query_opt=malicious"

    try:
        prepare_postgres_engine_args(raw_url)
        assert False, "Debería haber lanzado ValueError ante parámetro desconocido"
    except ValueError as exc:
        err_msg = str(exc)
        assert "Parámetro de conexión no soportado: 'invalid_query_opt'" in err_msg
        assert sensitive_pass not in err_msg, "Las credenciales no deben exponerse en el mensaje de error"
    print("  PASS | test_unsupported_parameters_rejected")


def test_supported_parameters_mapping():
    """Valida que connect_timeout y application_name se mapeen correctamente a connect_args."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=require&application_name=texeira_bot&connect_timeout=12"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert connect_args.get("application_name") == "texeira_bot"
    assert connect_args.get("timeout") == 12
    print("  PASS | test_supported_parameters_mapping")


def test_local_sqlite_fallback_intact():
    """Valida que en ausencia de DATABASE_URL se preserve el comportamiento local SQLite intacto."""
    orig = os.environ.get("DATABASE_URL")
    try:
        os.environ.pop("DATABASE_URL", None)
        assert is_postgres() is False
        assert get_database_url() is None

        os.environ["DATABASE_URL"] = ""
        assert is_postgres() is False
        assert get_database_url() is None
    finally:
        if orig is not None:
            os.environ["DATABASE_URL"] = orig
        else:
            os.environ.pop("DATABASE_URL", None)
    print("  PASS | test_local_sqlite_fallback_intact")


if __name__ == "__main__":
    print("============================================================")
    print("PRUEBAS DE ADAPTADOR NEON POSTGRESQL Y SEGURIDAD SSL")
    print("============================================================")
    test_neon_url_ssl_require()
    test_neon_url_ssl_verify_full()
    test_neon_url_ssl_verify_ca()
    test_neon_url_ssl_disable()
    test_channel_binding_require_explicitly_rejected()
    test_unsupported_parameters_rejected()
    test_supported_parameters_mapping()
    test_local_sqlite_fallback_intact()
    print("============================================================")
    print("RESULTADO: 8 PASS / 0 FAIL / 8 TOTAL — TODOS LOS TESTS APROBADOS")
    print("============================================================")
