"""
Prueba completa de los 4 fallos corregidos con variantes ES/EN.
Valida comportamiento real, no solo ausencia de errores.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import sys
sys.path.insert(0, '.')
import app

# ============================================================
# FALLO 1: Derivación falsa - Recomendar ≠ Transferir
# ============================================================
print("=" * 60)
print("FALLO 1: Recomendar un asesor no equivale a transferir")
print("=" * 60)

fal1_cases = [
    ("Contacta a un asesor para consultar los detalles", "ES directo"),
    ("Te recomiendo contactar a un asesor", "ES recomendar"),
    ("I recommend contacting an advisor", "EN recomendar"),
    ("Habla con un asesor para más info", "ES variante"),
    ("Talk to an agent for details", "EN variante"),
]

fal1_ok = 0
fal1_fail = 0
fal1_skip = 0
for msg, label in fal1_cases:
    r = app.rag_chain(msg, f'f1-{label}')
    if r.get('is_rate_limit'):
        fal1_skip += 1
        print(f"  [SKIP] {label}: rate limit activo, no evaluable")
        continue
    esc = r.get('is_escalation', False)
    res = r.get('resolved_autonomously', True)
    status = "OK" if (not esc and res) else "FALLO"
    if status == "FALLO":
        fal1_fail += 1
    else:
        fal1_ok += 1
    print(f"  [{status}] {label}: escalation={esc} resolved={res}")

print(f"  Resultado: {fal1_ok}/{fal1_ok+fal1_fail} pasaron ({fal1_skip} skip rate-limit)")

# ============================================================
# FALLO 2: Contacto de agencia - Fuentes externas vs Texeira
# ============================================================
print("\n" + "=" * 60)
print("FALLO 2: Fuentes externas NO son contacto de Texeira")
print("=" * 60)

fal2_cases = [
    ("¿Hay cupos disponibles para mañana?", "ES disponibilidad"),
    ("¿Tienen disponibilidad para Machu Picchu?", "ES disponibilidad tour"),
    ("Is there availability for tomorrow?", "EN disponibilidad"),
    ("Do you have spots available?", "EN disponibilidad variante"),
    ("¿Puedo reservar para mañana?", "ES reserva"),
]

fal2_ok = 0
fal2_fail = 0
fal2_skip = 0
for msg, label in fal2_cases:
    r = app.rag_chain(msg, f'f2-{label}')
    if r.get('is_rate_limit'):
        fal2_skip += 1
        print(f"  [SKIP] {label}: rate limit activo, no evaluable")
        continue
    needs = r.get('needs_agency_confirmation', False)
    resp = r['response'].lower()
    has_ext = any(x in resp for x in ['mptc.com.pe', 'touristico.com'])
    has_phone = '+51 953' in resp or '+51 984' in resp
    status = "OK" if (needs and not has_ext and has_phone) else "FALLO"
    if status == "FALLO":
        fal2_fail += 1
    else:
        fal2_ok += 1
    print(f"  [{status}] {label}: needs={needs} ext={has_ext} phone={has_phone}")

print(f"  Resultado: {fal2_ok}/{fal2_ok+fal2_fail} pasaron ({fal2_skip} skip rate-limit)")

# ============================================================
# FALLO 3: Condiciones pendientes en rutas deterministas
# ============================================================
print("\n" + "=" * 60)
print("FALLO 3: Rutas deterministas marcan condiciones pendientes")
print("=" * 60)

fal3_cases = [
    ("¿Cuál es el precio en soles de Salkantay?", "ES precio PEN"),
    ("¿Cuánto cuesta en soles Machu Picchu?", "ES precio PEN variante"),
    ("¿Cuál es el precio en PEN del Valle Sagrado?", "ES precio PEN tour"),
    ("What is the price in soles for Salkantay?", "EN precio PEN"),
    ("How much in PEN for the City Tour?", "EN precio PEN variante"),
    ("¿Cuánto cuesta el City Tour?", "ES precio USD (debe resolved=True)"),
]

fal3_ok = 0
fal3_fail = 0
fal3_skip = 0
for msg, label in fal3_cases:
    r = app.rag_chain(msg, f'f3-{label}')
    if r.get('is_rate_limit'):
        fal3_skip += 1
        print(f"  [SKIP] {label}: rate limit activo, no evaluable")
        continue
    res = r.get('resolved_autonomously', True)
    needs = r.get('needs_agency_confirmation', False)
    route = r.get('route', None)
    
    if "USD" in label:
        # Precio en USD no debe marcar pendiente
        status = "OK" if (res and not needs) else "FALLO"
    else:
        # Precio en PEN debe marcar pendiente
        status = "OK" if (not res and needs) else "FALLO"
    
    if status == "FALLO":
        fal3_fail += 1
    else:
        fal3_ok += 1
    print(f"  [{status}] {label}: resolved={res} needs={needs} route={route}")

print(f"  Resultado: {fal3_ok}/{fal3_ok+fal3_fail} pasaron ({fal3_skip} skip rate-limit)")

# ============================================================
# FALLO 4: Historial guarda respuesta final post-procesada
# ============================================================
print("\n" + "=" * 60)
print("FALLO 4: Historial contiene exactamente la respuesta final")
print("=" * 60)

fal4_cases = [
    ("¿Puedo pagar con Yape?", "ES pago Yape"),
    ("¿Aceptan tarjeta de crédito?", "ES pago tarjeta"),
    ("Can I pay with Yape?", "EN pago Yape"),
    ("Do you accept credit cards?", "EN pago tarjeta"),
    ("¿Cuánto es el adelanto?", "ES adelanto"),
]

fal4_ok = 0
fal4_fail = 0
fal4_skip = 0
for msg, label in fal4_cases:
    uid = f'f4-{label}'
    r = app.rag_chain(msg, uid)
    if r.get('is_rate_limit'):
        fal4_skip += 1
        print(f"  [SKIP] {label}: rate limit activo, no evaluable")
        continue
    hist = app.get_history(uid)
    last_ai = [m for m in hist if m['role'] == 'ai'][-1]['content']
    
    match = (last_ai == r['response'])
    has_contact = '+51' in last_ai
    status = "OK" if (match and has_contact) else "FALLO"
    if status == "FALLO":
        fal4_fail += 1
    else:
        fal4_ok += 1
    print(f"  [{status}] {label}: match={match} has_contact={has_contact}")

print(f"  Resultado: {fal4_ok}/{fal4_ok+fal4_fail} pasaron ({fal4_skip} skip rate-limit)")

# ============================================================
# RESUMEN TOTAL
# ============================================================
total_ok = fal1_ok + fal2_ok + fal3_ok + fal4_ok
total_fail = fal1_fail + fal2_fail + fal3_fail + fal4_fail
total_skip = fal1_skip + fal2_skip + fal3_skip + fal4_skip
total = total_ok + total_fail + total_skip

print("\n" + "=" * 60)
print(f"RESUMEN FALLOS 1-4: {total_ok}/{total} pasaron ({total_fail} fallos, {total_skip} skip rate-limit)")
print("=" * 60)
