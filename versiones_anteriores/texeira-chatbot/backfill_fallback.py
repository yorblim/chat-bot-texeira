"""
backfill_fallback.py — Migración retroactiva del flag resolved_autonomously.

Contexto: antes de la corrección híbrida, cuando el LLM generaba por su
cuenta el texto del fallback (p. ej. "Não dispongo de esa información
exacta..." en portugués), la interacción se registraba en la tabla
interactions con resolved_autonomously=1 aunque realmente era un fallback.
Este script re-evalúa las respuestas ya guardadas con la NUEVA lógica de
detección (app.is_fallback_response) y corrige retroactivamente
resolved_autonomously 1 → 0 donde corresponde.

Solo toca filas con interaction_type='llm' (no respuestas predefinidas
ni navegación de UI).

Uso:
  python backfill_fallback.py            # dry-run: solo reporta, no modifica
  python backfill_fallback.py --apply    # aplica la corrección
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Fuente única de verdad: la misma función que usa la cadena en producción.
from app import is_fallback_response

DB_PATH = str(ROOT / "texeira_logs.db")


def main():
    apply = "--apply" in sys.argv

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, bot_response, resolved_autonomously, interaction_type "
        "FROM interactions"
    ).fetchall()

    total_llm = 0
    to_fix = []
    already_ok = 0

    for r in rows:
        if r["interaction_type"] != "llm":
            continue
        total_llm += 1
        is_fb = is_fallback_response(r["bot_response"])
        if is_fb and r["resolved_autonomously"] == 1:
            to_fix.append(r["id"])
        elif is_fb and r["resolved_autonomously"] == 0:
            already_ok += 1

    print(f"Filas llm revisadas:                          {total_llm}")
    print(f"Filas a corregir (resolved_autonomously 1→0): {len(to_fix)}")
    print(f"Filas de fallback ya correctas (0):           {already_ok}")

    if to_fix and apply:
        for rid in to_fix:
            conn.execute(
                "UPDATE interactions SET resolved_autonomously = 0 WHERE id = ?",
                (rid,),
            )
        conn.commit()
        print("✔ Migración aplicada. Las métricas de /metrics ahora reflejan la realidad.")
    elif to_fix:
        print("Modo dry-run: ninguna fila modificada.")
        print("Ejecuta: python backfill_fallback.py --apply para aplicar los cambios.")
    else:
        print("No hay filas que corregir.")

    conn.close()


if __name__ == "__main__":
    main()
