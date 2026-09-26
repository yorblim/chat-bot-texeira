"""
test_normalize_query.py — Pruebas unitarias de normalización de consultas para el retriever.

Verifica los 4 requerimientos funcionales:
  1. Corrección de tildes y errores en palabras clave de tours (machu pichu -> machu picchu, montaña colores -> montaña de colores).
  2. Normalización de variantes comunes (waynapicchu -> wayna picchu, salkantai -> salkantay, etc.).
  3. Eliminación de caracteres especiales innecesarios (¿?¡!*~_#$%^&@ etc.).
  4. NO modificación de preguntas en inglés (preserva texto original).
"""

import sys
import os
from pathlib import Path

# Ajustar path al proyecto
sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from app import normalize_query, detect_language


def test_tildes_y_errores_palabras_clave():
    """1. Corrija tildes faltantes y ortografía típica en palabras clave de tours."""
    casos = [
        ("cuanto cuesta machu pichu", "cuanto cuesta machu picchu"),
        ("kiero ir a la montaña colores cuanto es", "kiero ir a la montaña de colores cuanto es"),
        ("informacion sobre montana colores", "informacion sobre montaña de colores"),
        ("montana de 7 colores precio", "montaña de 7 colores precio"),
        ("q incluye el tour del valle sagrao", "q incluye el tour del valle sagrado"),
        ("precio de canon del colca", "precio de cañón del colca"),
        ("detalles del tour mistico", "detalles del tour místico"),
    ]
    for entrada, esperado in casos:
        resultado = normalize_query(entrada)
        assert resultado == esperado, f"[1. Tildes] '{entrada}' -> Obtenido: '{resultado}', Esperado: '{esperado}'"
        print(f"  PASS | [1. Tildes] '{entrada}' -> '{resultado}'")


def test_normalizacion_variantes_comunes():
    """2. Normalice variantes comunes (wayna picchu, salkantay, humantay, vinicunca, etc.)."""
    casos = [
        ("boleto para wayna picchu", "boleto para wayna picchu"),
        ("como llegar a waynapicchu", "como llegar a wayna picchu"),
        ("boleto para huayna picchu", "boleto para wayna picchu"),
        ("subir a huaynapicchu desde aguas calientes", "subir a wayna picchu desde aguas calientes"),
        ("trekking a salkantai", "trekking a salkantay"),
        ("fotos de salkantay", "fotos de salkantay"),
        ("laguna umantay precio", "laguna humantay precio"),
        ("visita a montaña winicunca", "visita a montaña vinicunca"),
        ("camino a choquequiraw", "camino a choquequirao"),
        ("tour arqueologico waqrapukara", "tour arqueologico waqra pukara"),
        ("conocer el puente queswachaca", "conocer el puente q'eswachaca"),
    ]
    for entrada, esperado in casos:
        resultado = normalize_query(entrada)
        assert resultado == esperado, f"[2. Variantes] '{entrada}' -> Obtenido: '{resultado}', Esperado: '{esperado}'"
        print(f"  PASS | [2. Variantes] '{entrada}' -> '{resultado}'")


def test_eliminacion_caracteres_especiales():
    """3. Elimine caracteres especiales innecesarios."""
    casos = [
        ("¿¿¿cuanto cuesta machu pichu???", "cuanto cuesta machu picchu"),
        ("¡¡¡hola!!! ¿a ke hora sale el city tour?", "hola a ke hora sale el city tour"),
        ("precio de salkantai...?? #promo", "precio de salkantay promo"),
        ("tour @machupicchu!!! todo el dia", "tour machu picchu todo el dia"),
        ("información ***valle sagrao*** (full day)", "información valle sagrado full day"),
    ]
    for entrada, esperado in casos:
        resultado = normalize_query(entrada)
        assert resultado == esperado, f"[3. Especiales] '{entrada}' -> Obtenido: '{resultado}', Esperado: '{esperado}'"
        print(f"  PASS | [3. Especiales] '{entrada}' -> '{resultado}'")


def test_no_modificar_preguntas_en_ingles():
    """4. NO modifique preguntas en inglés."""
    casos_ingles = [
        "how much is machu pichu tour",
        "wat time does the tour start",
        "what is included in salkantai trek?",
        "can i book a tour for tomorrow?",
        "how do i get to waynapicchu from cusco?",
        "do you offer sacred valley tours?",
    ]
    for entrada in casos_ingles:
        resultado = normalize_query(entrada)
        assert resultado == entrada, f"[4. Inglés] '{entrada}' fue modificada a '{resultado}'"
        print(f"  PASS | [4. Inglés intacto] '{entrada}' == '{resultado}'")


def test_casos_borde():
    """Casos borde: strings vacíos, espacios en blanco, queries de una sola palabra."""
    assert normalize_query("") == ""
    assert normalize_query("   ") == ""
    assert normalize_query("machu pichu") == "machu picchu"
    assert normalize_query("waynapicchu") == "wayna picchu"
    assert normalize_query("salkantai") == "salkantay"
    print("  PASS | [5. Casos borde OK]")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EJECUTANDO TESTS DE NORMALIZACIÓN DE CONSULTAS (normalize_query)")
    print("=" * 60)
    test_tildes_y_errores_palabras_clave()
    test_normalizacion_variantes_comunes()
    test_eliminacion_caracteres_especiales()
    test_no_modificar_preguntas_en_ingles()
    test_casos_borde()
    print("\n" + "=" * 60)
    print("TODOS LOS TESTS DE normalize_query PASARON CON ÉXITO")
    print("=" * 60 + "\n")
