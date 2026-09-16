"""
run_ragas_multi.py — Múltiples corridas de la evaluación RAGAS con estadística.

Tesis: Agente Conversacional RAG — Texeira Travel Tour

Ejecuta la evaluación completa de run_ragas.py N_RUNS veces (por defecto 3),
reutilizando run_single_evaluation() (sin duplicar lógica), y calcula:

  - Por pregunta: promedio y desviación estándar de faithfulness y
    context_precision a través de las corridas.
  - Agregados globales separados por: (a) dentro de alcance,
    (b) fuera de alcance (fallback), (c) por idioma (es/en/pt).
  - Costo acumulado de todas las corridas (llamadas, tokens, USD estimados).

Exporta:
  - evaluation/resultados_ragas_final.csv: una fila por pregunta con las
    3 corridas + estadísticos de cada métrica.
  - evaluation/resumen_resultados.json: resumen citable en el capítulo de
    resultados (medias ± SD por idioma, fallback accuracy, significancia
    estadística y costo total).

Uso:
  python evaluation/run_ragas_multi.py

No modifica app.py, el system prompt ni la base de datos de producción.
"""

import io
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if not (hasattr(sys.stdout, "encoding") and str(sys.stdout.encoding).lower() == "utf-8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import csv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from run_ragas import (
    run_single_evaluation,
    load_dataset,
    tracker,
    DEEPSEEK_INPUT_USD_PER_M,
    DEEPSEEK_OUTPUT_USD_PER_M,
)

DATASET_PATH = Path(__file__).resolve().parent / "test_dataset.json"
CSV_PATH = Path(__file__).resolve().parent / "resultados_ragas_final.csv"
JSON_PATH = Path(__file__).resolve().parent / "resumen_resultados.json"
N_RUNS = 3

# Pausa entre corridas completas (cada corrida evalúa todas las preguntas).
# Si LLM_PROVIDER=groq, se recomienda al menos 2-3 segundos entre llamadas
# individuales; la pausa entre corridas adiciona margen extra de seguridad.
EVAL_DELAY_SECONDS = float(os.getenv("EVAL_DELAY_SECONDS", "0"))


def mean(values) -> float | None:
    return sum(values) / len(values) if values else None


def std(values) -> float:
    if len(values) >= 2:
        return statistics.stdev(values)
    return 0.0


def fmt(value) -> str:
    return "—" if value is None else f"{value:.4f}"


def welch_compare(final_rows: list[dict], langs: tuple[str, str]) -> dict:
    """
    Test de Welch (t de dos colas con varianzas desiguales) comparando la
    faithfulness por pregunta (promedio de las corridas) entre dos idiomas.
    """
    from scipy import stats

    a = [r["f_mean"] for r in final_rows if r["idioma"] == langs[0] and r["f_mean"] is not None]
    b = [r["f_mean"] for r in final_rows if r["idioma"] == langs[1] and r["f_mean"] is not None]

    if len(a) < 2 or len(b) < 2:
        return {
            "par": f"{langs[0]}-{langs[1]}",
            "p_valor": None,
            "significativo": None,
            "conclusion": f"Sin datos suficientes para comparar {langs[0]} y {langs[1]}.",
        }

    t_stat, p_valor = stats.ttest_ind(a, b, equal_var=False)
    p_valor = round(float(p_valor), 4)
    significativo = p_valor <= 0.05

    if significativo:
        conclusion = (
            f"Hay diferencia estadísticamente significativa entre {langs[0]} "
            f"y {langs[1]} (p={p_valor})."
        )
    else:
        conclusion = (
            f"No hay diferencia estadísticamente significativa entre "
            f"{langs[0]} y {langs[1]} (p={p_valor})."
        )

    return {
        "par": f"{langs[0]}-{langs[1]}",
        "p_valor": p_valor,
        "significativo": significativo,
        "conclusion": conclusion,
    }


def main():
    print("=" * 78)
    print(f"EVALUACIÓN RAGAS MÚLTIPLE — {N_RUNS} CORRIDAS CON ESTADÍSTICA")
    print("Texeira Travel Tour | Cadena real: app.rag_chain()")
    print("=" * 78)

    dataset = load_dataset(DATASET_PATH)
    print(f"Dataset: {len(dataset)} preguntas")

    runs_rows = []
    total_cost = {"rag_calls": 0, "judge_calls": 0, "input_tokens": 0, "output_tokens": 0}

    for run_idx in range(1, N_RUNS + 1):
        print(f"\n{'#' * 78}\n# CORRIDA {run_idx}/{N_RUNS}\n{'#' * 78}")
        results = run_single_evaluation(verbose=True)
        runs_rows.append(results["rows"])
        for k in total_cost:
            total_cost[k] += results["cost"].get(k, 0)
        print(f"\n  [corrida {run_idx}] llamadas: "
              f"{results['cost'].get('rag_calls', 0)} RAG + "
              f"{results['cost'].get('judge_calls', 0)} juez")
        # Pausa entre corridas para rate limits (crítico con Groq: 30 req/min)
        if run_idx < N_RUNS and EVAL_DELAY_SECONDS > 0:
            print(f"  Pausa de {EVAL_DELAY_SECONDS}s entre corridas...")
            time.sleep(EVAL_DELAY_SECONDS)

    # ---- Alinear por pregunta y calcular estadísticos ----
    n_dataset = len(dataset)
    if any(len(rows) != n_dataset for rows in runs_rows):
        print("  ✗ ERROR: el número de filas por corrida no coincide con el dataset.")
        sys.exit(1)

    final_rows = []
    for i, item in enumerate(dataset):
        q = item["question"]
        lang = item.get("language") or "es"
        scope = item.get("scope") or ("out_of_scope" if item.get("expected") == "fallback" else "in_scope")

        f_runs = [runs_rows[r][i]["faithfulness"] for r in range(N_RUNS)]
        cp_runs = [runs_rows[r][i]["context_precision"] for r in range(N_RUNS)]
        f_valid = [v for v in f_runs if v is not None]
        cp_valid = [v for v in cp_runs if v is not None]

        final_rows.append({
            "pregunta": q,
            "idioma": lang,
            "scope": scope,
            "f_runs": f_runs,
            "cp_runs": cp_runs,
            "f_mean": mean(f_valid),
            "f_std": std(f_valid),
            "cp_mean": mean(cp_valid),
            "cp_std": std(cp_valid),
        })

    # ---- CSV final ----
    csv_fields = [
        "pregunta", "idioma", "scope",
        "faithfulness_run1", "faithfulness_run2", "faithfulness_run3",
        "faithfulness_promedio", "faithfulness_desv_std",
        "context_precision_run1", "context_precision_run2", "context_precision_run3",
        "context_precision_promedio", "context_precision_desv_std",
    ]
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in final_rows:
            writer.writerow({
                "pregunta": r["pregunta"],
                "idioma": r["idioma"],
                "scope": r["scope"],
                **{f"faithfulness_run{k+1}": fmt(r["f_runs"][k]) for k in range(N_RUNS)},
                "faithfulness_promedio": fmt(r["f_mean"]),
                "faithfulness_desv_std": fmt(r["f_std"]),
                **{f"context_precision_run{k+1}": fmt(r["cp_runs"][k]) for k in range(N_RUNS)},
                "context_precision_promedio": fmt(r["cp_mean"]),
                "context_precision_desv_std": fmt(r["cp_std"]),
            })
    print(f"\n  → CSV final guardado en: {CSV_PATH}")

    # ---- Agregados por grupo ----
    in_scope_rows = [r for r in final_rows if r["scope"] == "in_scope"]
    out_scope_rows = [r for r in final_rows if r["scope"] == "out_of_scope"]

    def group_stats(rows, key_mean, key_std):
        values = [r[key_mean] for r in rows if r[key_mean] is not None]
        return (mean(values), std(values), len(values))

    in_f_mean, in_f_std, in_n = group_stats(in_scope_rows, "f_mean", "f_std")
    in_cp_mean, in_cp_std, _ = group_stats(in_scope_rows, "cp_mean", "cp_std")

    # Accuracy de fallback por corrida
    fb_accs = []
    for run_idx in range(N_RUNS):
        fb_total = 0
        fb_correct = 0
        for i, item in enumerate(dataset):
            if item.get("scope") == "out_of_scope":
                fb_total += 1
                if runs_rows[run_idx][i]["fallback_correct"]:
                    fb_correct += 1
        fb_accs.append((fb_correct / fb_total * 100) if fb_total else 100.0)

    # ---- Resumen ejecutivo (tabla lista para copiar) ----
    print("\n" + "=" * 78)
    print("RESUMEN EJECUTIVO — TABLA COMPARATIVA POR IDIOMA")
    print(f"(promedio ± desv. estándar de las {N_RUNS} corridas)")
    print("=" * 78)
    print(f"{'Idioma':<8} {'n':<4} {'Faithfulness':<28} {'Context Precision'}")
    print("-" * 78)
    for lang in ["es", "en", "pt"]:
        grp = [r for r in final_rows if r["idioma"] == lang]
        g_f_mean, g_f_std, g_n = group_stats(grp, "f_mean", "f_std")
        g_cp_mean, g_cp_std, _ = group_stats(grp, "cp_mean", "cp_std")
        print(f"{lang:<8} {g_n:<4} "
              f"{fmt(g_f_mean)} ± {fmt(g_f_std):<14} "
              f"{fmt(g_cp_mean)} ± {fmt(g_cp_std)}")

    print("\n--- Versión LaTeX (para el capítulo de resultados) ---")
    for lang in ["es", "en", "pt"]:
        grp = [r for r in final_rows if r["idioma"] == lang]
        g_f_mean, g_f_std, g_n = group_stats(grp, "f_mean", "f_std")
        g_cp_mean, g_cp_std, _ = group_stats(grp, "cp_mean", "cp_std")
        print(f"  {lang} & {g_n} & "
              f"{fmt(g_f_mean)} $\\pm$ {fmt(g_f_std)} & "
              f"{fmt(g_cp_mean)} $\\pm$ {fmt(g_cp_std)} \\\\")

    # ---- Agregados globales por scope ----
    print("\n" + "=" * 78)
    print("AGREGADOS GLOBALES POR ALCANCE")
    print("=" * 78)
    print(f"  (a) Dentro de alcance (n={in_n}):")
    print(f"        Faithfulness:       {fmt(in_f_mean)} ± {fmt(in_f_std)}")
    print(f"        Context Precision:  {fmt(in_cp_mean)} ± {fmt(in_cp_std)}")
    print(f"  (b) Fuera de alcance / fallback (n={len(out_scope_rows)}):")
    fb_mean, fb_std = mean(fb_accs), std(fb_accs)
    print(f"        Accuracy de fallback: {fb_mean:.2f}% ± {fb_std:.2f}% "
          f"({sum(1 for x in fb_accs if x == 100.0)}/{N_RUNS} corridas al 100%)")
    print(f"        (faithfulness/context_precision no aplican: son respuestas")
    print(f"         de fallback literal, sin métricas RAGAS)")
    print(f"  (c) Por idioma: ver tabla comparativa arriba.")

    # ---- Costo total acumulado ----
    total_calls = total_cost["rag_calls"] + total_cost["judge_calls"]
    total_usd = (
        total_cost["input_tokens"] / 1_000_000 * DEEPSEEK_INPUT_USD_PER_M
        + total_cost["output_tokens"] / 1_000_000 * DEEPSEEK_OUTPUT_USD_PER_M
    )
    print("\n" + "=" * 78)
    print(f"COSTO TOTAL ACUMULADO ({N_RUNS} CORRIDAS)")
    print("=" * 78)
    print(f"  Llamadas al LLM (respuestas RAG):  {total_cost['rag_calls']}")
    print(f"  Llamadas al LLM (juez RAGAS):      {total_cost['judge_calls']}")
    print(f"  Total de llamadas:                 {total_calls}")
    print(f"  Tokens de entrada (aprox.):        {total_cost['input_tokens']:,}")
    print(f"  Tokens de salida (aprox.):         {total_cost['output_tokens']:,}")
    print(f"  Costo estimado DeepSeek:           ${total_usd:.4f} USD")
    print(f"\n  CSV final: {CSV_PATH}")
    print("=" * 78)

    # ---- Test de Welch entre idiomas (faithfulness) ----
    print("\n" + "=" * 78)
    print("SIGNIFICANCIA ESTADÍSTICA — TEST DE WELCH ENTRE IDIOMAS")
    print("(scipy.stats.ttest_ind, equal_var=False, faithfulness por pregunta)")
    print("=" * 78)
    significancia = {"metodo": "Welch t-test de dos colas (scipy.stats.ttest_ind, equal_var=False)",
                     "variable": "faithfulness por pregunta (promedio de las corridas)",
                     "comparaciones": {}}
    for pair in [("es", "en"), ("es", "pt"), ("en", "pt")]:
        comp = welch_compare(final_rows, pair)
        significancia["comparaciones"][comp["par"]] = comp
        print(f"  {comp['par']:<6} → {comp['conclusion']}")

    # ---- Persistir resumen citable (resumen_resultados.json) ----
    por_idioma = {}
    for lang in ["es", "en", "pt"]:
        grp = [r for r in final_rows if r["idioma"] == lang]
        g_f_mean, g_f_std, g_n = group_stats(grp, "f_mean", "f_std")
        g_cp_mean, g_cp_std, _ = group_stats(grp, "cp_mean", "cp_std")
        por_idioma[lang] = {
            "n": g_n,
            "faithfulness_media": round(g_f_mean, 4) if g_f_mean is not None else None,
            "faithfulness_sd": round(g_f_std, 4),
            "context_precision_media": round(g_cp_mean, 4) if g_cp_mean is not None else None,
            "context_precision_sd": round(g_cp_std, 4),
        }

    resumen = {
        "fecha_evaluacion": time.strftime("%Y-%m-%d %H:%M:%S"),
        "num_corridas": N_RUNS,
        "dataset_size": len(dataset),
        "por_idioma": por_idioma,
        "agregado_in_scope": {
            "n": in_n,
            "faithfulness_media": round(in_f_mean, 4) if in_f_mean is not None else None,
            "faithfulness_sd": round(in_f_std, 4),
            "context_precision_media": round(in_cp_mean, 4) if in_cp_mean is not None else None,
            "context_precision_sd": round(in_cp_std, 4),
        },
        "fallback_accuracy": {
            "n": len(out_scope_rows),
            "accuracy_media": round((fb_mean / 100), 4),
            "accuracy_sd": round((fb_std / 100), 4),
        },
        "significancia_estadistica": significancia,
        "costo": {
            "llamadas_rag": total_cost["rag_calls"],
            "llamadas_juez": total_cost["judge_calls"],
            "tokens_entrada": total_cost["input_tokens"],
            "tokens_salida": total_cost["output_tokens"],
            "costo_usd_estimado": round(total_usd, 4),
        },
    }
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"\n  → Resumen guardado en: {JSON_PATH}")


if __name__ == "__main__":
    main()
