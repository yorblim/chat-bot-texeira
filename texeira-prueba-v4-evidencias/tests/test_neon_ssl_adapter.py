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


def test_channel_binding_require_allows_sasl_continue_and_final():
    """
    Valida que channel_binding=require acepte los mensajes 11 (AuthenticationSASLContinue)
    y 12 (AuthenticationSASLFinal), que forman parte del protocolo normal SASL de PostgreSQL.
    """
    dummy_conn = SecureConnection.__new__(SecureConnection)
    dummy_conn._channel_binding_mode = "require"
    dummy_conn.channel_binding = b"tls_binding_bytes"

    class DummyAuth:
        def __init__(self):
            self.server_first = None
            self.server_final = None
            self.mechanism_name = "SCRAM-SHA-256-PLUS"

        def set_server_first(self, data):
            self.server_first = data

        def get_client_final(self):
            return "c_final_data"

        def set_server_final(self, data):
            self.server_final = data

    dummy_conn.auth = DummyAuth()
    dummy_conn._send_message = lambda *args, **kwargs: None
    dummy_conn._sock = type("DummySock", (), {"flush": lambda self: None})()

    context_dummy = type("Ctx", (), {"error": None})()

    # Mensaje 11: AuthenticationSASLContinue (debe ser procesado sin lanzar excepción)
    sasl_continue_data = struct.pack("!i", 11) + b"r=servernonce,s=salt,i=4096"
    dummy_conn.handle_AUTHENTICATION_REQUEST(sasl_continue_data, context_dummy)
    assert dummy_conn.auth.server_first == "r=servernonce,s=salt,i=4096"

    # Mensaje 12: AuthenticationSASLFinal (debe ser procesado sin lanzar excepción)
    sasl_final_data = struct.pack("!i", 12) + b"v=server_signature_data"
    dummy_conn.handle_AUTHENTICATION_REQUEST(sasl_final_data, context_dummy)
    assert dummy_conn.auth.server_final == "v=server_signature_data"

    # Mensaje 0: AuthenticationOk (debe ser procesado sin lanzar excepción)
    auth_ok_data = struct.pack("!i", 0)
    dummy_conn.handle_AUTHENTICATION_REQUEST(auth_ok_data, context_dummy)

    print("  PASS | test_channel_binding_require_allows_sasl_continue_and_final")


def test_channel_binding_require_rejects_auth_ok_without_scram_plus():
    """
    Valida que channel_binding=require rechace AuthenticationOk (código 0) si no
    se completó previamente una negociación exitosa de SCRAM-SHA-256-PLUS:
    1. Si el servidor envía AuthenticationOk inmediatamente (ej. trust authentication) sin SASL.
    2. Si el servidor inició SASL pero saltó a AuthenticationOk antes de completar mensajes 11 y 12.
    """
    dummy_conn = SecureConnection.__new__(SecureConnection)
    dummy_conn._channel_binding_mode = "require"
    dummy_conn.channel_binding = b"tls_binding_bytes"
    dummy_conn._sasl_plus_completed = False
    dummy_conn.auth = None

    context_dummy = type("Ctx", (), {"error": None})()
    auth_ok_data = struct.pack("!i", 0)

    # Caso 1: Servidor envía AuthenticationOk inmediatamente (sin SASL)
    try:
        dummy_conn.handle_AUTHENTICATION_REQUEST(auth_ok_data, context_dummy)
        assert False, "Debería haber rechazado AuthenticationOk sin autenticación SASL previa"
    except pg8000.exceptions.InterfaceError as e:
        assert "se recibió AuthenticationOk sin haber completado la autenticación SCRAM-SHA-256-PLUS" in str(e)

    # Caso 2: Servidor inició SASL pero saltó a AuthenticationOk sin completar el handshake
    class IncompleteAuth:
        def __init__(self):
            self.mechanism_name = "SCRAM-SHA-256-PLUS"
            self.stage = type("Stage", (), {"name": "get_client_first"})()

    dummy_conn.auth = IncompleteAuth()
    try:
        dummy_conn.handle_AUTHENTICATION_REQUEST(auth_ok_data, context_dummy)
        assert False, "Debería haber rechazado AuthenticationOk con SASL incompleto"
    except pg8000.exceptions.InterfaceError as e:
        assert "se recibió AuthenticationOk sin haber completado la autenticación SCRAM-SHA-256-PLUS" in str(e)

    print("  PASS | test_channel_binding_require_rejects_auth_ok_without_scram_plus")


def test_scram_sha_256_plus_full_authentication_flow():
    """
    Valida un ciclo completo y exitoso de autenticación SCRAM-SHA-256-PLUS con channel_binding=require.
    Comprueba el intercambio íntegro de los 4 mensajes (10 -> InitialResponse, 11 -> Response, 12 -> Final, 0 -> Ok).
    """
    import scramp
    import scramp.core

    user = "neon_user"
    pwd = "super_secure_password_123"
    cb_data = ("tls-server-end-point", b"simulated_tls_exporter_binding_bytes_456")

    # Configuración del servidor SCRAM
    mech = scramp.core.ScramMechanism("SCRAM-SHA-256-PLUS")
    salt = scramp.core.Salt(b"test_salt_123456")
    salted_pwd = scramp.core._make_salted_password(mech.hf, pwd, salt, 4096)
    c_key, stored_key, s_key = scramp.core._c_key_stored_key_s_key(mech.hf, salted_pwd)

    def auth_fn(u):
        return (salt, stored_key, s_key, 4096)

    scram_server = scramp.core.ScramServer(mech, auth_fn, channel_binding=cb_data)

    # Crear conexión SecureConnection simulada
    conn = SecureConnection.__new__(SecureConnection)
    conn._channel_binding_mode = "require"
    conn.channel_binding = cb_data
    conn.user = user.encode("utf-8")
    conn.password = pwd.encode("utf-8")
    conn._client_encoding = "utf-8"

    sent_messages = []

    def mock_send_message(code, data):
        sent_messages.append((code, data))

    conn._send_message = mock_send_message
    conn._sock = type("DummySock", (), {"flush": lambda self: None})()

    context_dummy = type("Ctx", (), {"error": None})()

    # Paso 1: Servidor envía AuthenticationSASL (código 10) ofreciendo SCRAM-SHA-256 y SCRAM-SHA-256-PLUS
    msg10_data = struct.pack("!i", 10) + b"SCRAM-SHA-256\x00SCRAM-SHA-256-PLUS\x00\x00"
    conn.handle_AUTHENTICATION_REQUEST(msg10_data, context_dummy)

    # Verificar que el cliente seleccionó SCRAM-SHA-256-PLUS
    assert conn.auth.mechanism_name == "SCRAM-SHA-256-PLUS"
    assert len(sent_messages) == 1
    # Mensaje enviado por el cliente: mech + length + client_first
    client_first_payload = sent_messages[0][1]
    mech_name_sent, rest = client_first_payload.split(b"\x00", 1)
    assert mech_name_sent == b"SCRAM-SHA-256-PLUS"
    init_len = struct.unpack("!i", rest[:4])[0]
    client_first_str = rest[4:4 + init_len].decode("utf-8")

    # Servidor procesa client_first y genera server_first
    scram_server.set_client_first(client_first_str)
    server_first_str = scram_server.get_server_first()

    # Paso 2: Servidor envía AuthenticationSASLContinue (código 11) con server_first
    msg11_data = struct.pack("!i", 11) + server_first_str.encode("utf-8")
    conn.handle_AUTHENTICATION_REQUEST(msg11_data, context_dummy)

    # Verificar que el cliente envió client_final
    assert len(sent_messages) == 2
    client_final_str = sent_messages[1][1].decode("utf-8")

    # Servidor procesa client_final y genera server_final
    scram_server.set_client_final(client_final_str)
    server_final_str = scram_server.get_server_final()

    # Paso 3: Servidor envía AuthenticationSASLFinal (código 12) con server_final
    msg12_data = struct.pack("!i", 12) + server_final_str.encode("utf-8")
    conn.handle_AUTHENTICATION_REQUEST(msg12_data, context_dummy)

    # Paso 4: Servidor envía AuthenticationOk (código 0)
    msg0_data = struct.pack("!i", 0)
    conn.handle_AUTHENTICATION_REQUEST(msg0_data, context_dummy)

    print("  PASS | test_scram_sha_256_plus_full_authentication_flow (4 pasos SASL completados con éxito)")


def test_channel_binding_require_no_downgrade_in_prefer_and_allow():
    """
    Valida que channel_binding=require NO sufra degradación a 'disable':
    1. En sslmode=prefer: ante fallo de SSL, NO debe hacer fallback a no-SSL ni forzar 'disable'.
    2. En sslmode=allow: el primer intento sin SSL debe recibir 'require', no 'disable'.
    """
    recorded_calls = []

    class MockSecureConnection:
        def __init__(self, *args, **kwargs):
            recorded_calls.append(kwargs)
            sm = kwargs.get("sslmode")
            cb = kwargs.get("channel_binding_mode")
            ssl_ctx = kwargs.get("ssl_context")

            if sm == "prefer":
                if ssl_ctx is not False:
                    raise pg8000.exceptions.InterfaceError("Server refuses SSL")
            elif sm == "allow":
                if ssl_ctx is False:
                    if cb == "require":
                        raise pg8000.exceptions.InterfaceError(
                            "channel_binding=require solicitado, pero la conexión no es SSL o no se pudo establecer channel binding."
                        )

    orig_cls = globals().get("SecureConnection")
    globals()["SecureConnection"] = MockSecureConnection
    import db_adapter
    orig_adapter_conn = db_adapter.SecureConnection
    db_adapter.SecureConnection = MockSecureConnection

    try:
        # 1. Probar prefer con channel_binding=require
        recorded_calls.clear()
        try:
            secure_pg8000_connect(
                user="u",
                password="p",
                host="localhost",
                channel_binding="require",
                sslmode="prefer",
            )
            assert False, "Debería haber fallado sin degradar a fallback no-SSL"
        except pg8000.exceptions.InterfaceError as e:
            assert "Server refuses SSL" in str(e)
        # Debe haber intentado exactamente 1 vez (con SSL) y NUNCA haber forzado disable
        assert len(recorded_calls) == 1
        assert recorded_calls[0].get("channel_binding_mode") == "require"

        # 2. Probar allow con channel_binding=require
        recorded_calls.clear()
        secure_pg8000_connect(
            user="u",
            password="p",
            host="localhost",
            channel_binding="require",
            sslmode="allow",
        )
        # En allow, deben haberse ejecutado 2 intentos:
        # Intento 1: no-SSL con channel_binding_mode='require' (NO 'disable')
        # Intento 2: SSL con channel_binding_mode='require'
        assert len(recorded_calls) == 2
        assert recorded_calls[0].get("channel_binding_mode") == "require"
        assert recorded_calls[0].get("ssl_context") is False
        assert recorded_calls[1].get("channel_binding_mode") == "require"
        assert recorded_calls[1].get("ssl_context") is not False
    finally:
        globals()["SecureConnection"] = orig_cls
        db_adapter.SecureConnection = orig_adapter_conn

    print("  PASS | test_channel_binding_require_no_downgrade_in_prefer_and_allow")


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


def test_exception_sanitization_in_second_attempts():
    """
    Valida que las excepciones originadas en el segundo intento (fallback de prefer
    o segundo intento de allow) salgan rigurosamente sanitizadas y sin trazas encadenadas.
    """
    fictitious_secret = "fictitious_pass_xyz987"

    class FailingSecondAttemptConnection:
        call_count = 0

        def __init__(self, *args, **kwargs):
            FailingSecondAttemptConnection.call_count += 1
            sm = kwargs.get("sslmode")
            ssl_ctx = kwargs.get("ssl_context")

            if sm == "prefer":
                if ssl_ctx is not False:
                    raise pg8000.exceptions.InterfaceError("Server refuses SSL")
                else:
                    # Segundo intento (fallback)
                    raise pg8000.exceptions.DatabaseError(
                        f"authentication failed for user test with password={fictitious_secret}"
                    )
            elif sm == "allow":
                if ssl_ctx is False:
                    # Primer intento falla
                    raise socket.error("connection refused on non-ssl port")
                else:
                    # Segundo intento con SSL
                    raise pg8000.exceptions.InterfaceError(
                        f"SSL connection failed: credentials error password={fictitious_secret}"
                    )

    orig_cls = globals().get("SecureConnection")
    globals()["SecureConnection"] = FailingSecondAttemptConnection
    import db_adapter
    orig_adapter_conn = db_adapter.SecureConnection
    db_adapter.SecureConnection = FailingSecondAttemptConnection

    try:
        # 1. Fallo en segundo intento de prefer
        FailingSecondAttemptConnection.call_count = 0
        try:
            secure_pg8000_connect(
                user="u",
                password=fictitious_secret,
                host="localhost",
                channel_binding="prefer",
                sslmode="prefer",
            )
            assert False, "Debería haber fallado en el segundo intento de prefer"
        except pg8000.exceptions.DatabaseError as exc:
            exc_str = str(exc)
            assert fictitious_secret not in exc_str
            assert "password=***" in exc_str
            assert exc.__cause__ is None
            assert exc.__suppress_context__ is True
            tb = "".join(traceback.format_exception(exc))
            assert fictitious_secret not in tb

        # 2. Fallo en segundo intento de allow
        FailingSecondAttemptConnection.call_count = 0
        try:
            secure_pg8000_connect(
                user="u",
                password=fictitious_secret,
                host="localhost",
                channel_binding="prefer",
                sslmode="allow",
            )
            assert False, "Debería haber fallado en el segundo intento de allow"
        except pg8000.exceptions.InterfaceError as exc:
            exc_str = str(exc)
            assert fictitious_secret not in exc_str
            assert "password=***" in exc_str
            assert exc.__cause__ is None
            assert exc.__suppress_context__ is True
            tb = "".join(traceback.format_exception(exc))
            assert fictitious_secret not in tb
    finally:
        globals()["SecureConnection"] = orig_cls
        db_adapter.SecureConnection = orig_adapter_conn

    print("  PASS | test_exception_sanitization_in_second_attempts")


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
    test_channel_binding_require_allows_sasl_continue_and_final()
    test_channel_binding_require_rejects_auth_ok_without_scram_plus()
    test_scram_sha_256_plus_full_authentication_flow()
    test_channel_binding_require_no_downgrade_in_prefer_and_allow()
    test_exception_sanitization_no_leak_in_chain()
    test_sanitize_error_message_helper()
    test_exception_sanitization_in_second_attempts()
    test_tls_hostname_mismatch_rejection()
    test_tls_untrusted_certificate_rejection()
    test_tls_server_refuses_ssl_strict_rejection()
    test_tls_server_refuses_ssl_prefer_fallback()
    test_local_sqlite_fallback_intact()
    print("================================================================================")
    print("RESULTADO: 22 PASS / 0 FAIL / 22 TOTAL — TODOS LOS TESTS APROBADOS")
    print("================================================================================")
