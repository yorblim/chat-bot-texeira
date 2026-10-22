"""ver_db.py — Visualiza el contenido de las bases de datos para evidencia."""
import sqlite3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DBS = [
    (str(ROOT / "texeira_logs.db"),         "Catalogo de Tours (produccion)"),
    (str(ROOT / "state" / "trial_logs.db"), "Interacciones y metricas de investigacion"),
]

for db_path, descripcion in DBS:
    if not os.path.exists(db_path):
        print(f"[SKIP] No encontrada: {db_path}")
        continue

    print("=" * 60)
    print(f"BASE DE DATOS: {db_path}")
    print(f"Descripcion:   {descripcion}")
    print("=" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tablas = [t[0] for t in cursor.fetchall()]

    print("\n[TABLAS Y REGISTROS]")
    for nombre in tablas:
        try:
            cursor.execute("SELECT COUNT(*) FROM [" + nombre + "]")
            count = cursor.fetchone()[0]
            print(f"  - {nombre}: {count} registros")
        except Exception as e:
            print(f"  - {nombre}: ERROR {e}")

    tabla_main = "interactions" if "interactions" in tablas else (tablas[0] if tablas else None)
    if tabla_main:
        print(f"\n[COLUMNAS DE '{tabla_main}']")
        cursor.execute("PRAGMA table_info([" + tabla_main + "])")
        for col in cursor.fetchall():
            print(f"  [{col[0]}] {col[1]}  tipo={col[2]}")

    if "interactions" in tablas:
        print("\n[METRICAS DE INVESTIGACION]")

        cursor.execute("SELECT COUNT(*) FROM interactions WHERE interaction_type = 'llm'")
        total_llm = cursor.fetchone()[0]
        print(f"  Interacciones LLM reales:       {total_llm}")

        cursor.execute("SELECT COUNT(*) FROM interactions WHERE resolved_autonomously = 1 AND interaction_type = 'llm'")
        resueltas = cursor.fetchone()[0]
        print(f"  Resueltas autonomamente:         {resueltas}")

        if total_llm > 0:
            tasa = round(resueltas / total_llm * 100, 2)
            print(f"  Tasa de resolucion autonoma:     {tasa}%")

        cursor.execute("SELECT AVG(latency_ms) FROM interactions WHERE interaction_type = 'llm'")
        avg_lat = cursor.fetchone()[0]
        if avg_lat:
            print(f"  Latencia promedio (ms):          {round(avg_lat, 2)}")

        cursor.execute("SELECT COUNT(*) FROM interactions WHERE escalated_to_human = 1")
        escaladas = cursor.fetchone()[0]
        print(f"  Escaladas a humano:              {escaladas}")

        print("\n[DISTRIBUCION POR IDIOMA]")
        cursor.execute("SELECT detected_language, COUNT(*) FROM interactions GROUP BY detected_language ORDER BY COUNT(*) DESC")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} mensajes")

        print("\n[DISTRIBUCION POR CANAL]")
        cursor.execute("SELECT channel, COUNT(*) FROM interactions GROUP BY channel ORDER BY COUNT(*) DESC")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} mensajes")

        print("\n[ULTIMAS 5 INTERACCIONES]")
        cursor.execute(
            "SELECT id, timestamp, channel, detected_language, "
            "resolved_autonomously, latency_ms, escalated_to_human, interaction_type "
            "FROM interactions ORDER BY id DESC LIMIT 5"
        )
        for r in cursor.fetchall():
            print(f"  ID={r[0]} | {r[1]} | canal={r[2]} | lang={r[3]} | resuelto={r[4]} | lat={r[5]}ms | escalado={r[6]} | tipo={r[7]}")

    if "catalog_tours" in tablas:
        print("\n[TOURS EN EL CATALOGO]")
        cursor.execute("SELECT entity_id, name, official_price, currency, is_active FROM catalog_tours ORDER BY is_active DESC, name")
        for row in cursor.fetchall():
            estado = "ACTIVO" if row[4] else "inactivo"
            precio = f"{row[3]} {row[2]}" if row[2] else "precio por confirmar"
            print(f"  [{estado}] {row[1]} ({row[0]}) — {precio}")

    conn.close()
    print()

print("=" * 60)
print("FIN DEL REPORTE")
print("=" * 60)
