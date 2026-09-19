"""Prueba de los 4 puntos de REVISION_OPENCODE.md"""
import sys
sys.path.insert(0, ".")

from app import rag_chain

def test_punto1():
    """No registrar recomendaciones como derivaciones reales"""
    print("=== PUNTO 1: Derivación falsa ===")
    r = rag_chain("Quiero tour privado", "test_p1")
    # "contacta a un asesor" es orientación, no transferencia
    assert r["is_escalation"] == False, f"escalation={r['is_escalation']}"
    assert r["resolved_autonomously"] == True, f"resolved={r['resolved_autonomously']}"
    print("OK: recomendación no es derivación")

def test_punto2():
    """Distinguir fuentes externas del contacto de Texeira"""
    print("\n=== PUNTO 2: Contacto de agencia ===")
    # Pregunta sobre disponibilidad (condición comercial) para activar needs_agency
    r = rag_chain("¿Tienen disponibilidad para Machu Picchu mañana?", "test_p2")
    assert r["needs_agency_confirmation"] == True, f"needs_confirm={r['needs_agency_confirmation']}"
    resp = r["response"].lower()
    # No debe contener enlaces de otros operadores
    assert "mptc.com.pe" not in resp, "Contiene enlace externo"
    assert "touristico.com" not in resp, "Contiene enlace externo"
    # Debe contener teléfono de Texeira
    assert "+51 953" in resp or "+51 984" in resp, f"Sin teléfono Texeira: {r['response'][:200]}"
    print("OK: sin fuentes externas, con contacto Texeira")

def test_punto3():
    """Condiciones pendientes también en respuestas deterministas"""
    print("\n=== PUNTO 3: Ruta determinista ===")
    r = rag_chain("¿Cuál es el precio en soles de Salkantay?", "test_p3")
    assert r["resolved_autonomously"] == False, f"resolved={r['resolved_autonomously']}"
    assert r["needs_agency_confirmation"] == True, f"needs_confirm={r['needs_agency_confirmation']}"
    assert r.get("route") in ("evidence_unknown", "provisional_catalog"), f"route={r.get('route')}"
    print("OK: ruta determinista marca condición pendiente")

def test_punto4():
    """Historial guarda respuesta final post-procesada"""
    print("\n=== PUNTO 4: Historial post-procesado ===")
    uid = "test_p4_unico_777"
    r = rag_chain("¿Puedo pagar con Yape?", uid)
    # Verificar que el historial contiene la respuesta final
    from app import get_history
    hist = get_history(uid)
    last_resp = [m for m in hist if m["role"] == "ai"][-1]["content"]
    assert "+51" in last_resp, f"Historial sin teléfono: {last_resp[:150]}"
    assert last_resp == r["response"], "Historial no coincide con respuesta final"
    print("OK: historial guarda texto post-procesado")

if __name__ == "__main__":
    test_punto1()
    test_punto2()
    test_punto3()
    test_punto4()
    print("\n=== LOS 4 PUNTOS PASARON ===")
