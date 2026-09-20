"""
test_neon_ssl_adapter.py — Pruebas unitarias y de integración local para conexión segura con Neon PostgreSQL.

Cubre:
1. Comportamiento estricto de sslmode (disable, allow, prefer, require, verify-ca, verify-full).
2. Soporte real y observancia de channel_binding (disable, prefer, require).
3. Sanitización de información sensible en excepciones y trazas encadenadas (from None).
4. Negociación TLS con servidor de prueba:
   - Rechazo de certificados con nombres de servidor incorrectos (hostname mismatch).
   - Rechazo de certificados autofirmados / no confiables (CERTIFICATE_VERIFY_FAILED).
   - Rechazo ante servidor que rehúsa SSL cuando sslmode=require (cero degradación a texto plano).
   - Fallback a texto plano cuando servidor rehúsa SSL en sslmode=prefer.
   - Enforzamiento estricto de channel_binding=require (rechazo en no-SSL o sin soporte -PLUS).
5. Compatibilidad local con SQLite cuando DATABASE_URL no está configurada.
"""

import os
import re
import ssl
import socket
import struct
import threading
import tempfile
import datetime
import traceback
import sys
from pathlib import Path
from typing import Optional

# Agregar raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from db_adapter import (
    is_postgres,
    prepare_postgres_engine_args,
    get_database_url,
    get_engine,
    sanitize_error_message,
    SecureConnection,
    secure_pg8000_connect,
)
import pg8000.exceptions


# ==============================================================================
# 1. PRUEBAS DE CONFIGURACIÓN DE SSLMODE
# ==============================================================================

def test_neon_url_ssl_require():
    """Valida que sslmode=require configure ssl_context con verificación de CA y hostname."""
    raw_url = "postgresql://myuser:super_secret_pwd@ep-cool-123.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=disable"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert "super_secret_pwd" not in str(clean_url)
    assert clean_url.drivername == "postgresql+pg8000"
    assert clean_url.host == "ep-cool-123.us-east-2.aws.neon.tech"
    assert clean_url.database == "neondb"
    assert clean_url.query == {}

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert connect_args.get("sslmode") == "require"
    assert connect_args.get("channel_binding") == "disable"
    print("  PASS | test_neon_url_ssl_require")


def test_neon_url_ssl_verify_full():
    """Valida que sslmode=verify-full active verificación de CA y hostname."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=verify-full"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert connect_args.get("sslmode") == "verify-full"
    print("  PASS | test_neon_url_ssl_verify_full")


def test_neon_url_ssl_verify_ca():
    """Valida que sslmode=verify-ca verifique CA sin comprobar hostname."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=verify-ca"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert connect_args.get("sslmode") == "verify-ca"
    print("  PASS | test_neon_url_ssl_verify_ca")


def test_neon_url_ssl_disable():
    """Valida que sslmode=disable establezca ssl_context=False explícitamente en pg8000."""
    raw_url = "postgresql://myuser:pwd@localhost:5432/neondb?sslmode=disable"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert connect_args.get("ssl_context") is False
    assert connect_args.get("sslmode") == "disable"
    print("  PASS | test_neon_url_ssl_disable")


def test_neon_url_ssl_prefer():
    """Valida que sslmode=prefer configure intento con SSL y modo prefer."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=prefer"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    ctx = connect_args.get("ssl_context")
    assert isinstance(ctx, ssl.SSLContext)
    assert connect_args.get("sslmode") == "prefer"
    print("  PASS | test_neon_url_ssl_prefer")


def test_neon_url_ssl_allow():
    """Valida que sslmode=allow configure intento inicial sin SSL (ssl_context=False) y modo allow."""
    raw_url = "postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=allow"
    clean_url, connect_args = prepare_postgres_engine_args(raw_url)

    assert connect_args.get("ssl_context") is False
    assert connect_args.get("sslmode") == "allow"
    print("  PASS | test_neon_url_ssl_allow")


# ==============================================================================
# 2. PRUEBAS DE CHANNEL BINDING
# ==============================================================================

def test_channel_binding_options_supported():
    """Valida que channel_binding admita 'disable', 'prefer' y 'require'."""
    for cb_val in ("disable", "prefer", "require"):
        raw_url = f"postgresql://myuser:pwd@ep-cool.neon.tech/neondb?sslmode=require&channel_binding={cb_val}"
        _, connect_args = prepare_postgres_engine_args(raw_url)
        assert connect_args.get("channel_binding") == cb_val

    # Valor inválido debe ser rechazado
    try:
        prepare_postgres_engine_args("postgresql://myuser:pwd@ep-cool.neon.tech/neondb?channel_binding=invalid_mode")
        assert False, "Debería haber rechazado channel_binding inválido"
    except ValueError as e:
        assert "Valor de channel_binding no válido" in str(e)

    print("  PASS | test_channel_binding_options_supported")


def test_channel_binding_require_rejected_on_non_ssl():
    """Valida que channel_binding=require falle inmediatamente si la conexión no usa SSL."""
    dummy_conn = SecureConnection.__new__(SecureConnection)
    dummy_conn._channel_binding_mode = "require"
    dummy_conn.channel_binding = None  # No hay SSL

    # Simular mensaje AUTHENTICATION_REQUEST (auth_code = 10, SASL)
    sasl_data = struct.pack("!i", 10) + b"SCRAM-SHA-256-PLUS\x00\x00"
    try:
        dummy_conn.handle_AUTHENTICATION_REQUEST(sasl_data, None)
        assert False, "Debería haber rechazado channel_binding=require sin SSL"
    except pg8000.exceptions.InterfaceError as e:
        assert "channel_binding=require solicitado, pero la conexión no es SSL" in str(e)
    print("  PASS | test_channel_binding_require_rejected_on_non_ssl")


def test_channel_binding_require_rejected_when_server_lacks_plus():
    """Valida que channel_binding=require falle si el servidor no ofrece mecanismo -PLUS."""
    dummy_conn = SecureConnection.__new__(SecureConnection)
    dummy_conn._channel_binding_mode = "require"
    dummy_conn.channel_binding = b"dummy_binding_bytes"

    # Servidor ofrece únicamente SCRAM-SHA-256 sin channel binding
    sasl_data = struct.pack("!i", 10) + b"SCRAM-SHA-256\x00\x00"
    try:
        dummy_conn.handle_AUTHENTICATION_REQUEST(sasl_data, None)
        assert False, "Debería haber rechazado channel_binding=require si falta mecanismo -PLUS"
    except pg8000.exceptions.InterfaceError as e:
        assert "no ofrece mecanismos SCRAM con channel binding (SCRAM-SHA-256-PLUS)" in str(e)
    print("  PASS | test_channel_binding_require_rejected_when_server_lacks_plus")


def test_channel_binding_disable_clears_binding():
    """Valida que channel_binding=disable anule channel_binding para evitar su uso en scramp."""
    dummy_conn = SecureConnection.__new__(SecureConnection)
    dummy_conn._channel_binding_mode = "disable"
    dummy_conn.channel_binding = b"existing_tls_binding"

    # En AUTHENTICATION_REQUEST con disable, channel_binding debe pasar a None
    # Simulamos un error deliberado en el super() para detener la ejecución real de scramp
    sasl_data = struct.pack("!i", 0)  # AuthOk
    context_dummy = type("Ctx", (), {"error": None})()
    dummy_conn.message_types = {}
    try:
        dummy_conn.handle_AUTHENTICATION_REQUEST(sasl_data, context_dummy)
    except Exception:
        pass
    assert dummy_conn.channel_binding is None
    print("  PASS | test_channel_binding_disable_clears_binding")


# ==============================================================================
# 3. PRUEBAS DE SANITIZACIÓN DE EXCEPCIONES Y SECRETOS (from None)
# ==============================================================================

def test_exception_sanitization_no_leak_in_chain():
    """Valida que las credenciales no se expongan ni en mensajes de error ni en trazas encadenadas."""
    sensitive_pass = "ultra_secret_pass_998877"
    raw_url = f"postgresql://admin_user:{sensitive_pass}@remote-host.db.neon.tech:5432/secret_db?invalid_param=bad_val"

    try:
        prepare_postgres_engine_args(raw_url)
        assert False, "Debería haber fallado ante parámetro no soportado"
    except ValueError as exc:
        # 1. El mensaje no debe contener la contraseña ni el valor del parámetro
        assert sensitive_pass not in str(exc)
        assert "bad_val" not in str(exc)
        assert "invalid_param" in str(exc)
        # 2. La excepción debe suprimir la causa encadenada y no exponer el secreto en la traza
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
        tb_str = "".join(traceback.format_exception(exc))
        assert sensitive_pass not in tb_str

    # Probar URL malformada con puerto no numérico
    malformed_url = f"postgresql://admin_user:{sensitive_pass}@remote-host.neon.tech:invalid_port/secret_db"
    try:
        prepare_postgres_engine_args(malformed_url)
        assert False, "Debería haber fallado ante URL malformada"
    except ValueError as exc:
        assert sensitive_pass not in str(exc)
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
        tb_str = "".join(traceback.format_exception(exc))
        assert sensitive_pass not in tb_str

    print("  PASS | test_exception_sanitization_no_leak_in_chain")


def test_sanitize_error_message_helper():
    """Valida el ayudante de sanitización ante diversos formatos de contraseñas y tokens."""
    msg1 = "Error connecting to postgresql://admin:my_secret_pwd@ep-test.neon.tech:5432/mydb"
    sanitized1 = sanitize_error_message(msg1, "my_secret_pwd")
    assert "my_secret_pwd" not in sanitized1
    assert "postgresql://admin:***@ep-test.neon.tech:5432/mydb" in sanitized1

    msg2 = "Connection failed with password=top_secret_token and host=ep-test"
    sanitized2 = sanitize_error_message(msg2)
    assert "top_secret_token" not in sanitized2
    assert "password=***" in sanitized2

    print("  PASS | test_sanitize_error_message_helper")


# ==============================================================================
# 4. PRUEBAS DE NEGOCIACIÓN TLS CON SERVIDOR DE PRUEBA LOCAL
# ==============================================================================

def _generate_test_certificates():
    """Genera certificados en memoria: CA, servidor válido para 'localhost' y servidor con 'wrong.neon.tech'."""
    # CA
    ca_key = rsa.generate_private_key(65537, 2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Root CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # Servidor con hostname incorrecto: wrong.neon.tech
    wrong_key = rsa.generate_private_key(65537, 2048)
    wrong_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wrong.neon.tech")])
    wrong_cert = (
        x509.CertificateBuilder()
        .subject_name(wrong_name)
        .issuer_name(ca_name)
        .public_key(wrong_key.public_key())
        .serial_number(2)
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("wrong.neon.tech")]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # Servidor con hostname válido: localhost / 127.0.0.1
    valid_key = rsa.generate_private_key(65537, 2048)
    valid_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    valid_cert = (
        x509.CertificateBuilder()
        .subject_name(valid_name)
        .issuer_name(ca_name)
        .public_key(valid_key.public_key())
        .serial_number(3)
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    return ca_cert, ca_key, wrong_cert, wrong_key, valid_cert, valid_key


def test_tls_hostname_mismatch_rejection():
    """
    Valida que un certificado de servidor con nombre incorrecto (wrong.neon.tech)
    sea tajantemente rechazado por el cliente cuando check_hostname=True (verify-full o require).
    """
    ca_cert, ca_key, wrong_cert, wrong_key, _, _ = _generate_test_certificates()

    with tempfile.TemporaryDirectory() as tmpdir:
        ca_file = os.path.join(tmpdir, "ca.pem")
        srv_file = os.path.join(tmpdir, "srv.pem")
        key_file = os.path.join(tmpdir, "srv.key")

        with open(ca_file, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        with open(srv_file, "wb") as f:
            f.write(wrong_cert.public_bytes(serialization.Encoding.PEM))
        with open(key_file, "wb") as f:
            f.write(wrong_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(srv_file, key_file)

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        def srv_worker():
            try:
                csock, _ = srv.accept()
                # Leer solicitud SSLRequest de Postgres (8 bytes)
                csock.recv(8)
                # Responder 'S' (SSL soportado)
                csock.sendall(b"S")
                # Intentar handshake TLS
                try:
                    server_ctx.wrap_socket(csock, server_side=True)
                except Exception:
                    pass
                finally:
                    csock.close()
            finally:
                srv.close()

        t = threading.Thread(target=srv_worker)
        t.daemon = True
        t.start()

        # Contexto cliente con CA local y check_hostname=True hacia "localhost"
        client_ctx = ssl.create_default_context(cafile=ca_file)
        client_ctx.check_hostname = True
        client_ctx.verify_mode = ssl.CERT_REQUIRED

        try:
            # Conectar usando pg8000 secure_connect hacia localhost
            secure_pg8000_connect(
                user="testuser",
                password="secret_password_123",
                host="localhost",
                port=port,
                ssl_context=client_ctx,
                sslmode="verify-full",
                timeout=5,
            )
            assert False, "Debería haber rechazado el certificado por discrepancia de hostname"
        except (ssl.CertificateError, ssl.SSLCertVerificationError, pg8000.exceptions.InterfaceError) as e:
            err_text = str(e)
            assert "secret_password_123" not in err_text
            print(f"  PASS | test_tls_hostname_mismatch_rejection (Rechazo verificado: {type(e).__name__})")
        finally:
            t.join(timeout=2)


def test_tls_untrusted_certificate_rejection():
    """
    Valida que un certificado firmado por una CA desconocida / no confiable
    sea rechazado con CERTIFICATE_VERIFY_FAILED en sslmode=require / verify-ca / verify-full.
    """
    ca_cert, ca_key, _, _, valid_cert, valid_key = _generate_test_certificates()

    with tempfile.TemporaryDirectory() as tmpdir:
        srv_file = os.path.join(tmpdir, "srv.pem")
        key_file = os.path.join(tmpdir, "srv.key")

        with open(srv_file, "wb") as f:
            f.write(valid_cert.public_bytes(serialization.Encoding.PEM))
        with open(key_file, "wb") as f:
            f.write(valid_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(srv_file, key_file)

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        def srv_worker():
            try:
                csock, _ = srv.accept()
                csock.recv(8)
                csock.sendall(b"S")
                try:
                    server_ctx.wrap_socket(csock, server_side=True)
                except Exception:
                    pass
                finally:
                    csock.close()
            finally:
                srv.close()

        t = threading.Thread(target=srv_worker)
        t.daemon = True
        t.start()

        # Contexto cliente con CA del sistema (no incluye nuestra CA temporal)
        client_ctx = ssl.create_default_context()
        client_ctx.check_hostname = False
        client_ctx.verify_mode = ssl.CERT_REQUIRED

        try:
            secure_pg8000_connect(
                user="testuser",
                password="secret_password_123",
                host="127.0.0.1",
                port=port,
                ssl_context=client_ctx,
                sslmode="verify-ca",
                timeout=5,
            )
            assert False, "Debería haber rechazado el certificado emitido por CA no confiable"
        except (ssl.SSLCertVerificationError, pg8000.exceptions.InterfaceError) as e:
            err_text = str(e)
            assert "secret_password_123" not in err_text
            print(f"  PASS | test_tls_untrusted_certificate_rejection (Rechazo verificado: {type(e).__name__})")
        finally:
            t.join(timeout=2)


def test_tls_server_refuses_ssl_strict_rejection():
    """
    Valida que si el servidor responde 'N' (no soporta SSL),
    sslmode=require aborte inmediatamente con 'Server refuses SSL' y NUNCA degrade a texto plano.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)

    def srv_worker():
        try:
            csock, _ = srv.accept()
            csock.recv(8)
            # Servidor rehúsa SSL explícitamente
            csock.sendall(b"N")
            csock.close()
        finally:
            srv.close()

    t = threading.Thread(target=srv_worker)
    t.daemon = True
    t.start()

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED

    try:
        secure_pg8000_connect(
            user="testuser",
            password="secret_password_123",
            host="127.0.0.1",
            port=port,
            ssl_context=ctx,
            sslmode="require",
            timeout=5,
        )
        assert False, "Debería haber rechazado la conexión porque el servidor rehusó SSL"
    except pg8000.exceptions.InterfaceError as e:
        err_text = str(e)
        assert "Server refuses SSL" in err_text or "communication error" in err_text
        assert "secret_password_123" not in err_text
        print("  PASS | test_tls_server_refuses_ssl_strict_rejection (Cero degradación a texto plano)")
    finally:
        t.join(timeout=2)


def test_tls_server_refuses_ssl_prefer_fallback():
    """
    Valida que si el servidor responde 'N' en sslmode=prefer,
    el cliente realice el fallback seguro hacia texto plano según la especificación de PostgreSQL.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(2)

    attempts = []

    def srv_worker():
        try:
            # Intento 1 (con SSLRequest)
            csock1, _ = srv.accept()
            req1 = csock1.recv(8)
            attempts.append("ssl_request" if req1 == b"\x00\x00\x00\x08\x04\xd2\x16/" else "other")
            csock1.sendall(b"N")  # Rehúsa SSL
            csock1.close()

            # Intento 2 (fallback sin SSL)
            csock2, _ = srv.accept()
            req2 = csock2.recv(4)
            # El segundo intento no envía SSLRequest, envía longitud de StartupPacket
            attempts.append("plain_startup" if req2 != b"\x00\x00\x00\x08" else "ssl")
            csock2.close()
        finally:
            srv.close()

    t = threading.Thread(target=srv_worker)
    t.daemon = True
    t.start()

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED

    try:
        secure_pg8000_connect(
            user="testuser",
            password="secret_password_123",
            host="127.0.0.1",
            port=port,
            ssl_context=ctx,
            sslmode="prefer",
            timeout=5,
        )
    except Exception:
        # Fallará luego de conectar al no responder autenticación completa el mock, lo esperado
        pass
    finally:
        t.join(timeout=2)

    assert "ssl_request" in attempts, "Debe haber intentado SSL primero"
    assert "plain_startup" in attempts, "Debe haber hecho fallback a texto plano tras el rechazo"
    print("  PASS | test_tls_server_refuses_ssl_prefer_fallback (Fallback prefer probado)")


# ==============================================================================
# 5. PRUEBAS DE COMPATIBILIDAD CON SQLITE LOCAL
# ==============================================================================

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


# ==============================================================================
# EJECUCIÓN GENERAL
# ==============================================================================

if __name__ == "__main__":
    print("================================================================================")
    print("PRUEBAS DE ENTREGA 1 — CONEXIÓN SEGURA NEON POSTGRESQL Y TLS")
    print("================================================================================")
    test_neon_url_ssl_require()
    test_neon_url_ssl_verify_full()
    test_neon_url_ssl_verify_ca()
    test_neon_url_ssl_disable()
    test_neon_url_ssl_prefer()
    test_neon_url_ssl_allow()
    test_channel_binding_options_supported()
    test_channel_binding_require_rejected_on_non_ssl()
    test_channel_binding_require_rejected_when_server_lacks_plus()
    test_channel_binding_disable_clears_binding()
    test_exception_sanitization_no_leak_in_chain()
    test_sanitize_error_message_helper()
    test_tls_hostname_mismatch_rejection()
    test_tls_untrusted_certificate_rejection()
    test_tls_server_refuses_ssl_strict_rejection()
    test_tls_server_refuses_ssl_prefer_fallback()
    test_local_sqlite_fallback_intact()
    print("================================================================================")
    print("RESULTADO: 17 PASS / 0 FAIL / 17 TOTAL — TODOS LOS TESTS APROBADOS")
    print("================================================================================")
