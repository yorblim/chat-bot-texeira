"""
Pruebas: deteccion de idioma + intencion general de tours.
"""
import sys, os
sys.path.insert(0, r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")
os.chdir(r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")

import app

# --- Pruebas de deteccion de idioma ---
print("=" * 50)
print("DETECCION DE IDIOMA")
print("=" * 50)

lang_tests = [
    ("hola", "es"),
    ("que tours tienen?", "es"),
    ("que tours contiene?", "es"),
    ("qué tours ofrecen?", "es"),
    ("viajes", "es"),
    ("qué viajes ofrecen?", "es"),
    ("cuanto cuesta", "es"),
    ("quiero ver tours", "es"),
    ("what tours do you have?", "en"),
    ("what is the price?", "en"),
    ("how much does it cost?", "en"),
    ("quais passeios voces tem?", "pt"),
    ("quanto custa?", "pt"),
    ("quels circuits proposez-vous?", "fr"),
    ("combien ca coute?", "fr"),
]

all_lang_ok = True
for text, expected in lang_tests:
    result = app.detect_language(text)
    status = "OK" if result == expected else "FAIL"
    if status == "FAIL":
        all_lang_ok = False
    print(f"  [{status}] '{text}' => {result} (esperado: {expected})")

# --- Pruebas de intencion de tours ---
print()
print("=" * 50)
print("INTENCION DE LISTADO DE TOURS")
print("=" * 50)

tour_tests = [
    ("que tours tienen?", True),
    ("qué tours ofrecen?", True),
    ("viajes", True),
    ("qué viajes ofrecen?", True),
    ("que tours contiene?", True),
    ("tours", True),
    ("muéstrame los tours", True),
    ("quiero ver tours", True),
    ("paquetes", True),
    ("qué paquetes tienen?", True),
    ("what tours do you have?", True),
    ("cuanto cuesta el city tour", False),
    ("que incluye el salkantay", False),
    ("a que hora salen", False),
    ("quiero reservar", False),
    ("hola", False),
]

all_tour_ok = True
for text, should_detect in tour_tests:
    result = app.check_tour_intent(text, lang="es")
    detected = result is not None
    status = "OK" if detected == should_detect else "FAIL"
    if status == "FAIL":
        all_tour_ok = False
    print(f"  [{status}] '{text}' => tour_intent={detected} (esperado: {should_detect})")

# --- Prueba de respuesta dinamica ---
print()
print("=" * 50)
print("RESPUESTA DINAMICA (ejemplo)")
print("=" * 50)
resp = app.check_tour_intent("que tours tienen?", lang="es")
if resp:
    print(resp)
else:
    print("  No se genero respuesta")

# --- Prueba de que el RAG no se llama para tours generales ---
print()
print("=" * 50)
print("INTEGRACION: check_tour_intent evita fallback")
print("=" * 50)
resp_en = app.check_tour_intent("what tours do you have?", lang="en")
if resp_en:
    print("  'what tours do you have?' => respuesta generada (no fallback)")
    print(f"  Longitud: {len(resp_en)} chars")
else:
    print("  FAIL: no se genero respuesta")

# --- Resumen ---
print()
print("=" * 50)
if all_lang_ok and all_tour_ok:
    print("TODAS LAS PRUEBAS PASARON")
else:
    print("ALGUNAS PRUEBAS FALLARON")
print("=" * 50)
