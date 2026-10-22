"""ver_tabla.py — Muestra la tabla interactions como grilla para evidencia."""
import sqlite3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "state" / "trial_logs.db"

if not DB_PATH.exists():
    print(f"[SKIP] Base de datos no encontrada: {DB_PATH}")
    exit(0)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

print("=" * 80)
print(f"TABLA: interactions  ({DB_PATH})")
print("=" * 80)

cur.execute("""
    SELECT id, timestamp, channel, detected_language,
           resolved_autonomously, round(latency_ms,0), escalated_to_human, interaction_type
    FROM interactions
    ORDER BY id ASC
    LIMIT 25
""")
rows = cur.fetchall()
headers = ["id", "timestamp", "canal", "idioma", "resuelto", "lat_ms", "escalado", "tipo"]
widths  = [5,    26,          10,      7,         9,          9,        9,          12]

sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

def fila(vals):
    celdas = []
    for i, v in enumerate(vals):
        s = str(v) if v is not None else ""
        celdas.append(" " + s[:widths[i]].ljust(widths[i]) + " ")
    return "|" + "|".join(celdas) + "|"

print(sep)
print(fila(headers))
print(sep)
for r in rows:
    print(fila(r))
print(sep)

# Totales
cur.execute("SELECT COUNT(*) FROM interactions")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM interactions WHERE resolved_autonomously=1 AND interaction_type='llm'")
resueltos = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM interactions WHERE interaction_type='llm'")
llm = cur.fetchone()[0]

print()
print("=" * 80)
print("RESUMEN DE METRICAS")
print("=" * 80)
print(f"  Total de registros en 'interactions':   {total}")
print(f"  Interacciones LLM reales:               {llm}")
print(f"  Resueltas autonomamente (LLM):           {resueltos}")
if llm > 0:
    print(f"  Tasa de resolucion autonoma:            {round(resueltos/llm*100,2)}%")
cur.execute("SELECT AVG(latency_ms) FROM interactions WHERE interaction_type='llm'")
avg = cur.fetchone()[0]
if avg:
    print(f"  Latencia promedio LLM:                  {round(avg,2)} ms")
print()

print("DISTRIBUCION POR IDIOMA:")
cur.execute("SELECT detected_language, COUNT(*) as n FROM interactions GROUP BY detected_language ORDER BY n DESC")
for r in cur.fetchall():
    print(f"  {r[0]:6} -> {r[1]} mensajes")

print()
print("DISTRIBUCION POR CANAL:")
cur.execute("SELECT channel, COUNT(*) as n FROM interactions GROUP BY channel ORDER BY n DESC")
for r in cur.fetchall():
    print(f"  {r[0]:12} -> {r[1]} mensajes")

conn.close()
print("=" * 80)
