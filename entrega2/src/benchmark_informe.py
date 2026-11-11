"""Gráficos, deriva y comparación con la corrida corta del benchmark (Fase 6).

Lee los datos crudos de ``salidas/benchmark/<corrida>/tiempo/ronda_*.npz`` y escribe en
``informe/``:

- ``benchmark_tiempo_boxplot.png``: tiempo por consulta por configuración (A–E agregadas),
  escala logarítmica. Caja = Q1–Q3, línea = mediana, bigotes = percentiles 1 y 99 (con
  500.000 valores por caja los puntos atípicos serían miles; el MIN y el MAX van en la Tabla 1).
- ``benchmark_deriva_por_ronda.png``: mediana por ronda de cada configuración relativa a su
  mediana global, con la banda de ±10 %.
- ``benchmark_deriva.csv``: mediana del primer y el último cuarto de las rondas por
  configuración (y por par), cambio en % y si supera el 10 %.
- ``benchmark_completa_vs_corta.{md,csv}``: medianas de la completa frente a la corta.

Uso:
    python src/benchmark_informe.py [--corrida completa] [--corta corta]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import BENCH_DIR, BLOQUE, CONFIGS, NOMBRE, PARES, _leer_tiempo  # noqa: E402
from config import ENTREGA2_DIR  # noqa: E402
from graficos import GRILLA, SERIES, SUPERFICIE, TINTA, TINTA2, _ejes  # noqa: E402

INFORME = ENTREGA2_DIR / "informe"
UMBRAL_DERIVA = 0.10
LIMITE_EJE_DERIVA = 40.0  # % ; el eje del gráfico de deriva se recorta aquí
COLOR_MODELO = {"tfidf": SERIES[0], "lsi": SERIES[1]}


def _idx(m: str, o: str) -> list[int]:
    return [k for k, p in enumerate(PARES) if p[:2] == (m, o)]


def _fmt(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def boxplot(ms: np.ndarray, ruta: Path, n_rep: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

    datos = [ms[_idx(m, o)].ravel() for m, o in CONFIGS]
    fig, ax = plt.subplots(figsize=(8.4, 4.8), dpi=200)
    fig.patch.set_facecolor(SUPERFICIE)
    _ejes(ax, f"Tiempo de respuesta por consulta (A–E agregadas, {n_rep:,} repeticiones por par)".replace(",", "."),
          "", "ms por consulta (escala logarítmica)")
    bp = ax.boxplot(datos, whis=(1, 99), showfliers=False, widths=0.55, patch_artist=True,
                    medianprops={"color": TINTA, "linewidth": 2}, whiskerprops={"color": TINTA2, "linewidth": 1},
                    capprops={"color": TINTA2, "linewidth": 1}, boxprops={"linewidth": 0})
    for caja, (m, _) in zip(bp["boxes"], CONFIGS):
        caja.set_facecolor(COLOR_MODELO[m])
        caja.set_alpha(0.85)
    ax.set_yscale("log")
    lo = min(np.percentile(d, 1) for d in datos)
    hi = max(np.percentile(d, 99) for d in datos)
    ticks = [t for t in (0.2, 0.3, 0.5, 1, 2, 3, 5, 10, 20, 30, 50) if lo / 1.3 <= t <= hi * 1.3]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.set_ylim(lo / 1.25, hi * 1.25)
    ax.set_xticks(range(1, len(CONFIGS) + 1), [NOMBRE[c].replace(" + ", "\n+ ") for c in CONFIGS])
    ax.grid(False, axis="x")
    for i, d in enumerate(datos, 1):  # etiqueta directa: la mediana, a la derecha de la caja
        med = float(np.median(d))
        ax.annotate(_fmt(med, 2), (i + 0.3, med), xytext=(2, 0), textcoords="offset points", va="center",
                    color=TINTA, fontsize=7.5)
    ax.legend(handles=[Patch(facecolor=COLOR_MODELO["tfidf"], label="TF-IDF"),
                       Patch(facecolor=COLOR_MODELO["lsi"], label="LSI")], frameon=False, fontsize=8,
              labelcolor=TINTA2, loc="upper right")
    fig.text(0.01, 0.01, "Caja: Q1–Q3; línea: mediana (rotulada); bigotes: percentiles 1 y 99. "
             "Reloj: CLOCK_MONOTONIC_RAW.", color=TINTA2, fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def medianas_por_ronda(ms: np.ndarray) -> dict[tuple, np.ndarray]:
    n_rondas = ms.shape[1] // BLOQUE
    out = {}
    for m, o in CONFIGS:
        sub = ms[_idx(m, o)]
        out[(m, o)] = np.array([np.median(sub[:, r * BLOQUE:(r + 1) * BLOQUE]) for r in range(n_rondas)])
    return out


def grafico_deriva(ms: np.ndarray, ruta: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    por_ronda = medianas_por_ronda(ms)
    n = ms.shape[1] // BLOQUE
    rel = {c: 100 * (v / float(np.median(ms[_idx(*c)])) - 1) for c, v in por_ronda.items()}
    # Eje recortado para que la banda de ±10 % se lea; los puntos fuera de escala se rotulan.
    lim = min(LIMITE_EJE_DERIVA, max(12.0, max(float(np.abs(v).max()) for v in rel.values()) * 1.1))
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.6), dpi=200, sharex=True, sharey=True)
    fig.patch.set_facecolor(SUPERFICIE)
    q = n // 4
    for ax, (m, o) in zip(axes.ravel(), CONFIGS):
        _ejes(ax, NOMBRE[(m, o)], "", "")
        ax.axhspan(-100 * UMBRAL_DERIVA, 100 * UMBRAL_DERIVA, color=GRILLA, alpha=0.6, linewidth=0, zorder=1)
        ax.axhline(0, color=TINTA2, linewidth=1, zorder=2)
        for x0 in (q, n - q):
            ax.axvline(x0 - 0.5, color=TINTA2, linewidth=0.8, linestyle=(0, (2, 3)), zorder=2)
        v = rel[(m, o)]
        ax.plot(np.arange(n), np.clip(v, -lim, lim), color=COLOR_MODELO[m], linewidth=1.5, zorder=3)
        fuera = np.flatnonzero(np.abs(v) > lim)
        if fuera.size:
            k = int(fuera[np.argmax(np.abs(v[fuera]))])
            ax.annotate(f"máx. {v[k]:+.0f} % (ronda {k + 1})".replace("-", "−"), (k, np.sign(v[k]) * lim),
                        xytext=(6, -4), textcoords="offset points", color=TINTA2, fontsize=7, va="top")
        ax.set_ylim(-lim, lim)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} %".replace("+0 %", "0 %")))
    for ax in axes[1]:
        ax.set_xlabel("ronda (1.000 repeticiones por par)", color=TINTA2, fontsize=8.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("mediana de la ronda vs. global", color=TINTA2, fontsize=8.5)
    fig.suptitle("Deriva: mediana por ronda relativa a la mediana global (banda gris = ±10 %; eje recortado a ±40 %; "
                 "líneas punteadas = primer y último cuarto)", color=TINTA, fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def deriva(ms: np.ndarray) -> list[dict]:
    n = ms.shape[1] // BLOQUE
    q = n // 4
    ini, fin = slice(0, q * BLOQUE), slice((n - q) * BLOQUE, n * BLOQUE)
    filas = []
    for m, o in CONFIGS:
        grupos = [("A–E", _idx(m, o))] + [(PARES[k][2], [k]) for k in _idx(m, o)]
        for consulta, idx in grupos:
            a, b = float(np.median(ms[idx][:, ini])), float(np.median(ms[idx][:, fin]))
            cambio = b / a - 1
            filas.append({"configuracion": NOMBRE[(m, o)], "consulta": consulta, "rondas_primer_cuarto": f"1–{q}",
                          "rondas_ultimo_cuarto": f"{n - q + 1}–{n}", "mediana_primer_cuarto_ms": round(a, 4),
                          "mediana_ultimo_cuarto_ms": round(b, 4), "cambio_pct": round(100 * cambio, 2),
                          "supera_10pct": abs(cambio) > UMBRAL_DERIVA})
    return filas


def comparar(ms: np.ndarray, ms_corta: np.ndarray) -> list[dict]:
    filas = []
    for m, o in CONFIGS:
        for consulta, idx in [("A–E", _idx(m, o))] + [(PARES[k][2], [k]) for k in _idx(m, o)]:
            a, b = float(np.median(ms_corta[idx])), float(np.median(ms[idx]))
            filas.append({"configuracion": NOMBRE[(m, o)], "consulta": consulta, "mediana_corta_ms": round(a, 4),
                          "mediana_completa_ms": round(b, 4), "cambio_pct": round(100 * (b / a - 1), 2)})
    return filas


def _csv(ruta: Path, filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrida", default="completa")
    ap.add_argument("--corta", default="corta")
    a = ap.parse_args(argv)
    ms = _leer_tiempo(BENCH_DIR / a.corrida / "tiempo") / 1e6
    ms_corta = _leer_tiempo(BENCH_DIR / a.corta / "tiempo") / 1e6
    boxplot(ms, INFORME / "benchmark_tiempo_boxplot.png", ms.shape[1])
    grafico_deriva(ms, INFORME / "benchmark_deriva_por_ronda.png")
    der = deriva(ms)
    _csv(INFORME / "benchmark_deriva.csv", der)
    comp = comparar(ms, ms_corta)
    _csv(INFORME / "benchmark_completa_vs_corta.csv", comp)

    md = ["## Deriva: mediana del primer vs. el último cuarto de las rondas (ms)", "",
          "| Configuración | Primer cuarto | Último cuarto | Cambio | ¿> 10 %? |", "|---|---:|---:|---:|---|"]
    for f in der:
        if f["consulta"] == "A–E":
            md.append(f"| {f['configuracion']} | {_fmt(f['mediana_primer_cuarto_ms'])} | "
                      f"{_fmt(f['mediana_ultimo_cuarto_ms'])} | {_fmt(f['cambio_pct'], 1)} % | "
                      f"{'**sí**' if f['supera_10pct'] else 'no'} |")
    pares = [f for f in der if f["consulta"] != "A–E" and f["supera_10pct"]]
    md += ["", "Pares (configuración × consulta) con cambio > 10 %: "
           + (", ".join(f"{f['configuracion']} {f['consulta']} ({_fmt(f['cambio_pct'], 1)} %)" for f in pares)
              if pares else "ninguno"), "",
           f"## Medianas: corrida completa ({ms.shape[1]:,} rep.) vs. corta ({ms_corta.shape[1]:,} rep.), ms".replace(",", "."),
           "", "| Configuración | Corta | Completa | Cambio | Por consulta A / B / C / D / E (completa) |",
           "|---|---:|---:|---:|---|"]
    for m, o in CONFIGS:
        f = next(x for x in comp if x["configuracion"] == NOMBRE[(m, o)] and x["consulta"] == "A–E")
        por = " / ".join(_fmt(x["mediana_completa_ms"], 2) for x in comp
                         if x["configuracion"] == NOMBRE[(m, o)] and x["consulta"] != "A–E")
        md.append(f"| {f['configuracion']} | {_fmt(f['mediana_corta_ms'])} | {_fmt(f['mediana_completa_ms'])} | "
                  f"{_fmt(f['cambio_pct'], 1)} % | {por} |")
    texto = "\n".join(md) + "\n"
    (INFORME / "benchmark_completa_vs_corta.md").write_text(texto, encoding="utf-8")
    print(texto)
    print("-> informe/benchmark_tiempo_boxplot.png, benchmark_deriva_por_ronda.png, benchmark_deriva.csv, "
          "benchmark_completa_vs_corta.{md,csv}")


if __name__ == "__main__":
    main()
