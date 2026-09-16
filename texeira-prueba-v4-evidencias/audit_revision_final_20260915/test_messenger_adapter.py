"""
Pruebas unitarias para el adaptador de Facebook Messenger en app.py.
Verifica parsing del payload de Meta, deduplicación, eco y funciones de envío
sin realizar llamadas de red externas ni requerir tokens reales.
"""
import asyncio
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import app
from app import app as fastapi_app, send_messenger_message

client = TestClient(fastapi_app)


def test_send_messenger_message_no_token():
    """Si FB_PAGE_ACCESS_TOKEN está vacío, retorna False de forma segura sin error."""
    with patch.object(app, "FB_PAGE_ACCESS_TOKEN", ""):
        result = send_messenger_message(text="Hola", psid="123456789")
        assert result is False, "Debe retornar False cuando no hay token configurado"


def test_webhook_get_verification():
    """Verifica que el endpoint GET /webhook responda el challenge si el token coincide."""
    test_token = "mi_token_de_prueba_123"
    with patch.object(app, "META_VERIFY_TOKEN", test_token):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": test_token,
                "hub.challenge": "CHALLENGE_ACCEPTED_987",
            },
        )
        assert response.status_code == 200
        assert response.text == "CHALLENGE_ACCEPTED_987"


def test_webhook_messenger_echo_ignored():
    """Un mensaje de eco (donde sender == recipient) debe responder 200 con echo=True."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID_100",
                "time": 1726400000,
                "messaging": [
                    {
                        "sender": {"id": "PAGE_ID_100"},
                        "recipient": {"id": "PAGE_ID_100"},
                        "message": {"mid": "mid.echo123", "text": "Mensaje propio"},
                    }
                ],
            }
        ],
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("echo") is True


def test_webhook_messenger_inbound_success():
    """Un mensaje entrante válido de Messenger debe retornar 200 con status: ok y message_id."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID_100",
                "time": 1726400000,
                "messaging": [
                    {
                        "sender": {"id": "PSID_USER_789"},
                        "recipient": {"id": "PAGE_ID_100"},
                        "message": {
                            "mid": "mid.msg_test_001",
                            "text": "¿Qué tours tienen?",
                        },
                    }
                ],
            }
        ],
    }
    with patch.object(app, "FB_APP_SECRET", ""):
        with patch.object(app.database, "is_duplicate_webhook", return_value=False):
            response = client.post("/webhook", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "ok"
            assert data.get("message_id") == "mid.msg_test_001"


def test_webhook_messenger_deduplication():
    """Si el message_id ya fue procesado, se descarta por deduplicación devolviendo dedup=True."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID_100",
                "time": 1726400000,
                "messaging": [
                    {
                        "sender": {"id": "PSID_USER_789"},
                        "recipient": {"id": "PAGE_ID_100"},
                        "message": {
                            "mid": "mid.msg_duplicate_002",
                            "text": "Hola de nuevo",
                        },
                    }
                ],
            }
        ],
    }
    with patch.object(app, "FB_APP_SECRET", ""):
        with patch.object(app.database, "is_duplicate_webhook", return_value=True):
            response = client.post("/webhook", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data.get("dedup") is True


if __name__ == "__main__":
    test_send_messenger_message_no_token()
    test_webhook_get_verification()
    test_webhook_messenger_echo_ignored()
    test_webhook_messenger_inbound_success()
    test_webhook_messenger_deduplication()
    print("ALL MESSENGER ADAPTER TESTS PASSED!")
