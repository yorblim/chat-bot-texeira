import os
import sys
if os.environ.get('TEXEIRA_ISOLATED_TEST') != '1':
    raise SystemExit('Run: python tests/run_isolated.py test_flexible_tour_rates.py')
from datetime import date, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import app
import catalog_service
import verified_routes

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS | {name}")
    else:
        FAILED += 1
        print(f"  FAIL | {name} :: {detail}")

def run_tests():
    global PASSED, FAILED
    print("=" * 60)
    print("TEST: SISTEMA DE TARIFAS FLEXIBLES / ESPECIALES")
    print("=" * 60)

    test_entity = "camino-inka"
    # Aseguramos que no haya tarifas previas de prueba
    prev_rates = catalog_service.get_tour_rates(test_entity, active_only=False)
    for r in prev_rates:
        catalog_service.delete_tour_rate(r['id'], test_entity)

    # ---------------------------------------------------------
    # 1. Chatbot SIN tarifa especial registrada
    # ---------------------------------------------------------
    print("\n--- 1. Chatbot: Consulta de tarifa especial SIN registro previo ---")
    res_no_student = app.rag_chain("¿Hay tarifa para estudiantes en el Camino Inca?", "test_rates_user_1")
    check("Ruta evidence_no_special_rate", res_no_student.get('route') == 'evidence_no_special_rate' or res_no_student.get('response_route') == 'evidence_no_special_rate', f"route={res_no_student.get('route')}")
    check("No inventa descuento", "no disponemos de una tarifa especial" in res_no_student['response'].lower() and "estudiante" in res_no_student['response'].lower(), f"response={res_no_student['response'][:120]}")
    check("Menciona tarifa oficial base", any(w in res_no_student['response'] for w in ["tarifa oficial", "persona"]), f"response={res_no_student['response']}")

    # Consulta en inglés sin registro
    res_en_no_student = app.rag_chain("Do you have student discount for inca trail?", "test_rates_user_en_1")
    check("English no student rate", "do not have a registered special rate" in res_en_no_student['response'].lower() and "student" in res_en_no_student['response'].lower(), f"response={res_en_no_student['response'][:120]}")

    # ---------------------------------------------------------
    # 2. CRUD y Persistencia DB de Tarifas
    # ---------------------------------------------------------
    print("\n--- 2. CRUD de Tarifas en Base de Datos ---")
    today = date.today().isoformat()
    future_date = (date.today() + timedelta(days=60)).isoformat()
    past_date = (date.today() - timedelta(days=10)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Inserción de tarifa estudiante activa
    rate_student_data = {
        'entity_id': test_entity,
        'category': 'student',
        'name': 'Tarifa Universitaria ISIC/SUNEDU',
        'price': 520.00,
        'currency': 'USD',
        'conditions': 'Carnet universitario vigente y pasaporte (menores de 25 años)',
        'valid_from': today,
        'valid_to': future_date,
        'is_active': 1
    }
    ok_st, r_id = catalog_service.upsert_tour_rate(rate_student_data)
    check("Insercion de tarifa estudiante retorna ID", ok_st and int(r_id) > 0, f"r_id={r_id}")

    rates = catalog_service.get_tour_rates(test_entity, active_only=True)
    check("Consulta retorna 1 tarifa activa", len(rates) == 1, f"len={len(rates)}")
    if rates:
        check("Datos de tarifa correctos", rates[0]['rate_category'] == 'student' and float(rates[0]['price']) == 520.00, f"rate={rates[0]}")

    # Inserción de promoción vencida
    expired_promo_data = {
        'entity_id': test_entity,
        'category': 'promo',
        'name': 'Promo Black Friday Pasada',
        'price': 450.00,
        'currency': 'USD',
        'conditions': 'Valido solo en fin de semana',
        'valid_from': past_date,
        'valid_to': yesterday,
        'is_active': 1
    }
    ok_exp, exp_id = catalog_service.upsert_tour_rate(expired_promo_data)
    check("Insercion de promo vencida", ok_exp and int(exp_id) > 0)

    # get_tour_rates con filtro de fecha actual no debe incluir la vencida
    rates_active_today = catalog_service.get_tour_rates(test_entity, active_only=True, date_str=today)
    check("Filtro omite tarifa vencida", len(rates_active_today) == 1 and rates_active_today[0]['id'] == r_id, f"count={len(rates_active_today)}")

    # ---------------------------------------------------------
    # 3. Chatbot CON tarifa especial activa registrada
    # ---------------------------------------------------------
    print("\n--- 3. Chatbot: Consulta de tarifa especial CON registro activo ---")
    res_student = app.rag_chain("¿Cuánto cuesta el Camino Inca para estudiantes universitarios?", "test_rates_user_2")
    check("Ruta evidence_special_rate", res_student.get('route') == 'evidence_special_rate' or res_student.get('response_route') == 'evidence_special_rate', f"route={res_student.get('route')}")
    check("Muestra precio especial exacto", "520" in res_student['response'], f"response={res_student['response'][:140]}")
    check("Muestra requisitos/condiciones", "Carnet universitario vigente" in res_student['response'], f"response={res_student['response'][:140]}")
    check("Muestra fecha vigencia", future_date in res_student['response'], f"response={res_student['response'][:140]}")

    # Consulta en inglés con registro
    res_student_en = app.rag_chain("How much is student ticket for inca trail?", "test_rates_user_en_2")
    check("English special rate route", res_student_en.get('route') == 'evidence_special_rate' or res_student_en.get('response_route') == 'evidence_special_rate')
    check("English shows price and requirements", "520" in res_student_en['response'] and "Requirements" in res_student_en['response'])

    # ---------------------------------------------------------
    # 4. Consulta de precio general incluye mención de tarifas especiales
    # ---------------------------------------------------------
    print("\n--- 4. Chatbot: Precio general menciona disponibilidad de tarifas especiales ---")
    res_general_price = app.rag_chain("¿Cuál es el precio del Camino Inca?", "test_rates_user_3")
    check("Precio general responde", len(res_general_price['response']) > 20)
    check("Menciona disponibilidad de tarifas especiales", "tarifas especiales" in res_general_price['response'].lower() or "estudiante" in res_general_price['response'].lower(), f"response={res_general_price['response']}")

    # ---------------------------------------------------------
    # 5. Modificación y Eliminación de Tarifa
    # ---------------------------------------------------------
    print("\n--- 5. Modificacion y Eliminacion ---")
    # Actualizar precio de estudiante
    update_data = dict(rates[0])
    update_data['price'] = 499.00
    catalog_service.upsert_tour_rate(update_data)
    rates_updated = catalog_service.get_tour_rates(test_entity, active_only=True)
    check("Precio actualizado a 499.00", len(rates_updated) == 1 and float(rates_updated[0]['price']) == 499.00, f"price={rates_updated[0]['price']}")

    # Eliminar tarifas de prueba para dejar base de datos limpia
    del_ok1, _ = catalog_service.delete_tour_rate(r_id, test_entity)
    del_ok2, _ = catalog_service.delete_tour_rate(exp_id, test_entity)
    check("Eliminacion de tarifa estudiante", del_ok1)
    check("Eliminacion de promo vencida", del_ok2)

    remaining = catalog_service.get_tour_rates(test_entity, active_only=False)
    check("No quedan tarifas residuales de prueba", len(remaining) == 0, f"remaining={remaining}")

    print("\n" + "=" * 60)
    print(f"RESULTADOS: {PASSED} pasados, {FAILED} fallados")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
