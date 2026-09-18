import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Pruebas unitarias para la notificación push de derivación al WhatsApp del asesor humano.
Verifica que:
1. Se envíe mensaje formateado al teléfono del asesor cuando created=True.
2. El mensaje contenga ticket, canal, cliente, consulta y enlace al panel.
3. No se envíe notificación cuando created=False (ticket repetido).
4. No falle si ADVISOR_WHATSAPP_PHONE está ausente.
5. Los errores en el envío se capturen sin romper el flujo del usuario.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import handoff_support as h


def test_notify_advisor_success():
    """Verifica que notify_advisor invoque send_fn con el teléfono y mensaje correcto."""
    mock_send = MagicMock(return_value=True)
    row = {
        "id": "tkt_abc123",
        "channel": "whatsapp",
        "user_id": "+51984000111",
        "question": "¿Tienen tours a la montaña de 7 colores para mañana?",
        "created_at": "2026-09-15T12:00:00Z",
    }
    phone = "+51984123456"
    result = h.notify_advisor(row, send_fn=mock_send, advisor_phone=phone)

    assert result is True
    assert mock_send.call_count == 1
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["to_phone"] == phone
    text = call_kwargs["text"]
    assert "tkt_abc123" in text
    assert "whatsapp" in text
    assert "+51984000111" in text
    assert "montaña de 7 colores" in text
    assert "8023/handoffs" in text
    print("PASS: test_notify_advisor_success")


def test_notify_advisor_no_phone():
    """Si no hay teléfono configurado, retorna False de forma segura sin error."""
    mock_send = MagicMock()
    row = {"id": "tkt_001", "channel": "test", "user_id": "u1", "question": "hola"}

    old_phone = os.environ.get("ADVISOR_WHATSAPP_PHONE")
    try:
        if "ADVISOR_WHATSAPP_PHONE" in os.environ:
            del os.environ["ADVISOR_WHATSAPP_PHONE"]
        result = h.notify_advisor(row, send_fn=mock_send, advisor_phone="")
        assert result is False
        assert mock_send.call_count == 0
    finally:
        if old_phone is not None:
            os.environ["ADVISOR_WHATSAPP_PHONE"] = old_phone
    print("PASS: test_notify_advisor_no_phone")


def test_notify_advisor_send_exception_handled():
    """Si el envío lanza una excepción, se maneja de forma segura retornando False."""
    mock_send = MagicMock(side_effect=RuntimeError("Network timeout"))
    row = {"id": "tkt_002", "channel": "whatsapp", "user_id": "u2", "question": "precio"}
    result = h.notify_advisor(row, send_fn=mock_send, advisor_phone="+51984123456")
    assert result is False
    print("PASS: test_notify_advisor_send_exception_handled")


def test_apply_request_triggers_notification_only_once():
    """Verifica que apply_request llame a notify_advisor cuando created=True y NO cuando ya existe."""
    with tempfile.TemporaryDirectory() as folder:
        h.DB = Path(folder) / "requests_test.db"
        mock_send = MagicMock(return_value=True)

        ns = {
            "get_history": lambda uid: [{"role": "human", "content": "quiero asesor"}],
            "conversation_history": {},
            "send_whatsapp_message": mock_send,
            "ADVISOR_WHATSAPP_PHONE": "+51984111222",
            "ADVISOR_NOTIFICATIONS_ENABLED": True,
            "detect_language": lambda q: "es",
        }

        # 1. Primera solicitud -> se crea ticket y se notifica
        rag_input = {"handoff_requested": True, "handoff_language": "es"}
        res1 = h.apply_request(ns, rag_input, "user_100", "whatsapp", "quiero asesor")
        assert res1["handoff_registered"] is True
        ticket1 = res1["handoff_id"]
        assert mock_send.call_count == 1
        assert ticket1 in mock_send.call_args[1]["text"]

        # 2. Segunda solicitud del mismo usuario -> mismo ticket abierto, NO se re-notifica
        mock_send.reset_mock()
        res2 = h.apply_request(ns, rag_input, "user_100", "whatsapp", "asesor por favor")
        assert res2["handoff_id"] == ticket1
        assert mock_send.call_count == 0  # no se vuelve a llamar

        h.apply_request(ns, rag_input, 'synthetic', 'test', 'asesor')
        assert mock_send.call_count == 0
        ns['ADVISOR_NOTIFICATIONS_ENABLED'] = False
        h.apply_request(ns, rag_input, 'disabled', 'whatsapp', 'asesor')
        assert mock_send.call_count == 0

    print("PASS: test_apply_request_triggers_notification_only_once")


if __name__ == "__main__":
    test_notify_advisor_success()
    test_notify_advisor_no_phone()
    test_notify_advisor_send_exception_handled()
    test_apply_request_triggers_notification_only_once()
    print("ALL ADVISOR NOTIFICATION TESTS PASSED!")
