"""Tabla "antes / después" de la prueba preliminar de las 6 configuraciones (Fase 4b).

Antes = hiperparámetros elegidos con documentos completos (``*_antes.*``); después = elegidos con
consultas cortas. Lee ``informe/prueba_preliminar_optim_{top5,recall}{_antes,}.csv`` y
``informe/memoria_busqueda{_antes,}.json`` y escribe ``informe/prueba_preliminar_antes_despues.md``.

Uso:
    python src/comparar_antes_despues.py
"""
from __future__ import annotations

import csv
import json

from config import ENTREGA2_DIR

INFORME = ENTREGA2_DIR / "informe"
CONFIGS = [(m, o) for m in ("tfidf", "lsi") for o in ("ninguna", "kmeans", "lsh")]


def _top5(sufijo: str) -> dict:
    """(modelo, optim, consulta) -> (relevantes en top-5, resultados en top-5)."""
    out: dict = {}
    for f in csv.DictReader(open(INFORME / f"prueba_preliminar_optim_top5{sufijo}.csv", encoding="utf-8")):
        k = (f["modelo"], f["optim"], f["consulta"])
        rel, n = out.get(k, (0, 0))
        if f["rango"]:
            out[k] = (rel + (f["relevante"] == "True"), n + 1)
        else:
            out[k] = (rel, n)
    return out


def _recall(sufijo: str) -> dict:
    return {(f["modelo"], f["optim"], f["consulta"]): f
            for f in csv.DictReader(open(INFORME / f"prueba_preliminar_optim_recall{sufijo}.csv", encoding="utf-8"))}


def main() -> None:
    t_a, t_d = _top5("_antes"), _top5("")
    r_a, r_d = _recall("_antes"), _recall("")
    m_a = json.loads((INFORME / "memoria_busqueda_antes.json").read_text())
    m_d = json.loads((INFORME / "memoria_busqueda.json").read_text())
    nombre = {"ninguna": "exhaustiva", "kmeans": "K-Means", "lsh": "LSH"}

    def celda_top5(t, k):
        rel, n = t.get(k, (0, 0))
        return "vacío" if n == 0 else f"{rel}/{n}"

    lineas = ["## Relevantes en el top-5 (antes → después)", "",
              "| Configuración | A | B | C | D | E |", "|---|---|---|---|---|---|"]
    for m, o in CONFIGS:
        celdas = []
        for c in "ABCDE":
            a, d = celda_top5(t_a, (m, o, c)), celda_top5(t_d, (m, o, c))
            celdas.append(a if a == d else f"{a} → **{d}**")
        lineas.append(f"| {m.upper()} {nombre[o]} | " + " | ".join(celdas) + " |")
    lineas += ["", "## Recall relativo top-10 con tolerancia / estricto (antes → después)", "",
               "| Configuración | A | B | C | D | Media A–D (tol.) |", "|---|---|---|---|---|---|"]
    filas_csv = []
    for m, o in CONFIGS:
        if o == "ninguna":
            continue
        celdas, med_a, med_d = [], [], []
        for c in "ABCD":
            a, d = r_a[(m, o, c)], r_d[(m, o, c)]
            fa = f"{float(a['recall_tolerante']):.1f} / {float(a['recall_estricto']):.1f}"
            fd = f"{float(d['recall_tolerante']):.1f} / {float(d['recall_estricto']):.1f}"
            celdas.append(fa if fa == fd else f"{fa} → **{fd}**")
            med_a.append(float(a["recall_tolerante"]))
            med_d.append(float(d["recall_tolerante"]))
            filas_csv.append({"modelo": m, "optim": o, "consulta": c,
                              "recall_tol_antes": a["recall_tolerante"], "recall_tol_despues": d["recall_tolerante"],
                              "recall_estr_antes": a["recall_estricto"], "recall_estr_despues": d["recall_estricto"],
                              "examinados_antes": a["examinados"], "examinados_despues": d["examinados"],
                              "relevantes_top5_antes": t_a.get((m, o, c), (0, 0))[0],
                              "relevantes_top5_despues": t_d.get((m, o, c), (0, 0))[0]})
        lineas.append(f"| {m.upper()} {nombre[o]} | " + " | ".join(celdas)
                      + f" | {sum(med_a) / 4:.2f} → **{sum(med_d) / 4:.2f}** |")
    lineas += ["", "## Memoria del proceso de búsqueda (RSS, MiB)", "",
               "| Momento | Antes | Después |", "|---|---|---|"]
    for k, et in (("despues_de_cargar_indices", "Con todos los índices cargados"),
                  ("despues_de_las_30_consultas", "Tras las 30 consultas")):
        lineas.append(f"| {et} | {m_a[k]['rss_mib']} | {m_d[k]['rss_mib']} |")
    lineas.append(f"| Pico (VmHWM) | {m_a['despues_de_las_30_consultas']['pico_rss_mib']} | "
                  f"{m_d['despues_de_las_30_consultas']['pico_rss_mib']} |")
    texto = "\n".join(lineas) + "\n"
    (INFORME / "prueba_preliminar_antes_despues.md").write_text(texto, encoding="utf-8")
    with open(INFORME / "prueba_preliminar_antes_despues.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas_csv[0]))
        w.writeheader()
        w.writerows(filas_csv)
    print(texto)
    print("-> informe/prueba_preliminar_antes_despues.md / .csv")


if __name__ == "__main__":
    main()
