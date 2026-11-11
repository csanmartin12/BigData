"""Construye el índice TF-IDF + LSI desde MongoDB y lo guarda en ``entrega2/indice/``.

1. Corpus desde ``eso.xshooter.header`` (modo de campos ``texto`` por defecto).
2. TF-IDF manual (``tfidf.py``).
3. SVD completa de la matriz términos × documentos; k = menor k que alcanza el umbral (90 %)
   según el criterio (``sin_primera`` por defecto, ``energia`` opcional; ver ``lsi.py``).
   **No usa las consultas A–E.**
4. Verificaciones numéricas: reconstrucción con k = rango completo y docs proyectados = V_k.
5. Persistencia (``indice.py``), curvas (``informe/lsi_varianza.csv``) y gráfico
   (``informe/lsi_varianza_explicada.png``).

Uso:
    python src/construir_indice.py [--modo texto|todos] [--idf suavizado|clasico]
                                   [--criterio sin_primera|energia] [--umbral 0.90]
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

import lsi
import tfidf
from config import ENTREGA2_DIR, MONGO_COLECCION, MONGO_DB, MONGO_URI
from corpus import MODO_POR_DEFECTO, MODOS, construir_corpus
from indice import INDICE_DIR, guardar

INFORME = ENTREGA2_DIR / "informe"
UMBRALES = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)


def grafico_varianza(s: np.ndarray, umbral: float, k_energia: int, k_sin_primera: int, ruta, subtitulo: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, NullLocator

    superficie, tinta, tinta2, grilla = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    azul, naranja = "#2a78d6", "#eb6834"  # series 1 y 2 de la paleta de referencia
    e = 100 * lsi.varianza_explicada_acumulada(s)
    sp = 100 * lsi.varianza_sin_primera_acumulada(s)
    k_e, k_sp = np.arange(1, s.size + 1), np.arange(2, s.size + 1)

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200)
    fig.patch.set_facecolor(superficie)
    ax.set_facecolor(superficie)
    ax.plot(k_e, e, color=azul, linewidth=2, solid_capstyle="round", zorder=3,
            label="energia: Σ(i≤k) σᵢ² / Σ σᵢ²")
    ax.plot(k_sp, sp, color=naranja, linewidth=2, solid_capstyle="round", zorder=3,
            label="sin_primera: Σ(2≤i≤k) σᵢ² / Σ(i≥2) σᵢ²  (elegido)")
    ax.axhline(100 * umbral, color=tinta2, linewidth=1, zorder=2)
    ax.text(s.size, 100 * umbral + 1.2, f"umbral {100 * umbral:.0f} %", color=tinta2, ha="right", va="bottom",
            fontsize=9)
    for k, valor, color, dy in ((k_energia, e[k_energia - 1], azul, 12),
                                (k_sin_primera, sp[k_sin_primera - 2], naranja, -20)):
        ax.scatter([k], [valor], s=64, color=color, edgecolors=superficie, linewidths=2, zorder=4)
        ax.annotate(f"k = {k}  ({valor:.1f} %)".replace(".", ","), (k, valor), xytext=(9, dy),
                    textcoords="offset points", color=tinta, fontsize=10)
    ax.set_xscale("log")
    ticks = [t for t in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if t < s.size] + [s.size]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_xlim(0.9, s.size * 1.1)
    ax.set_ylim(0, 102)
    ax.set_xlabel("k (dimensiones latentes, escala logarítmica)", color=tinta2)
    ax.set_ylabel("σ² acumulada / σ² total (%)", color=tinta2)
    ax.set_title(f"LSI: varianza explicada acumulada — {subtitulo}", color=tinta, fontsize=11, loc="left")
    ax.grid(True, color=grilla, linewidth=1, linestyle="-")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(grilla)
    ax.tick_params(colors=tinta2, labelsize=9)
    leyenda = ax.legend(loc="lower right", frameon=False, fontsize=9)
    for t in leyenda.get_texts():
        t.set_color(tinta)
    fig.tight_layout()
    fig.savefig(ruta, facecolor=superficie)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", choices=MODOS, default=MODO_POR_DEFECTO)
    ap.add_argument("--idf", choices=tfidf.VARIANTES_IDF, default="suavizado")
    ap.add_argument("--criterio", choices=lsi.CRITERIOS, default=lsi.CRITERIO_POR_DEFECTO)
    ap.add_argument("--umbral", type=float, default=lsi.UMBRAL_POR_DEFECTO)
    ap.add_argument("--salida", default=str(INDICE_DIR))
    args = ap.parse_args()

    t0 = time.perf_counter()
    corpus = construir_corpus(args.modo)
    t_corpus = time.perf_counter() - t0
    t0 = time.perf_counter()
    tf = tfidf.ajustar(corpus.tokens, args.idf)
    t_tfidf = time.perf_counter() - t0
    x = tf.matriz
    print(f"Corpus ({args.modo}): N = {corpus.n}, |V| = {len(tf.vocabulario)}, nnz = {x.nnz} "
          f"(densidad {x.nnz / (x.shape[0] * x.shape[1]):.4%}); lectura+tokenización {t_corpus:.1f} s, "
          f"TF-IDF {t_tfidf:.1f} s")

    t0 = time.perf_counter()
    xd = x.toarray()
    a = xd.T  # términos × documentos
    u, s, vt = lsi.svd(a)
    t_svd = time.perf_counter() - t0
    modelo, chequeo = lsi.ajustar(x, umbral=args.umbral, usv=(u, s, vt), criterio=args.criterio)
    media = xd.mean(axis=0)
    gram = xd @ xd.T
    diag = {
        "sigma1_cuadrado_sobre_total": float(s[0] ** 2 / (s ** 2).sum()),
        "energia_vector_medio_sobre_total": float((media @ media) * corpus.n / (s ** 2).sum()),
        "coseno_medio_entre_documentos": float((gram.sum() - np.trace(gram)) / (corpus.n * (corpus.n - 1))),
    }
    k_tabla = {c: {f"{x_:.2f}": lsi.elegir_k(s, x_, c) for x_ in UMBRALES} for c in lsi.CRITERIOS}
    print(f"SVD completa ({t_svd:.1f} s): {s.size} valores singulares, rango numérico {chequeo['rango_numerico']}, "
          f"σ² total = {float((s ** 2).sum()):.3f}; σ1..σ5 = {np.round(s[:5], 2).tolist()}")
    print(f"Diagnóstico: {diag}")
    for c, tabla in k_tabla.items():
        print(f"  k por umbral ({c}): {tabla}")
    print(f"k elegido = {modelo.k} (criterio {args.criterio}, umbral {args.umbral:.0%}); "
          f"σ² acumulada/total en k = {modelo.varianza_k:.4f}; sin la primera = {modelo.varianza_sin_primera_k:.4f}")
    print(f"Verificación docs_k = Σ_k⁻¹ U_kᵀ d vs V_k: máx |dif| = {chequeo['max_abs_docs_k_menos_V_k']:.2e}")
    rec = lsi.reconstruir(*lsi.truncar(u, s, vt, s.size))
    err = float(np.abs(rec - a).max())
    print(f"Reconstrucción U Σ Vᵀ con k = {s.size} (rango completo): máx |A − UΣVᵀ| = {err:.2e}")

    man = guardar(Path(args.salida), corpus.ids, tf, modelo, modo=args.modo, hash_entrada=corpus.hash_entrada,
                  fuente=f"{MONGO_URI} {MONGO_DB}.{MONGO_COLECCION}, campo header",
                  extra={"verificaciones": {**chequeo, "max_abs_reconstruccion_rango_completo": err},
                         "diagnostico_espectro": diag, "k_por_umbral": k_tabla})
    print(f"Índice guardado en {args.salida}: {sum(v['bytes'] for v in man['archivos'].values()) / 1e6:.1f} MB, "
          f"hash de entrada {man['hash_datos_entrada'][:16]}…")

    e = lsi.varianza_explicada_acumulada(s)
    sp = lsi.varianza_sin_primera_acumulada(s)
    with open(INFORME / "lsi_varianza.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["k", "sigma", "sigma2", "acumulada_energia", "acumulada_sin_primera"])
        for i, sv in enumerate(s, 1):
            w.writerow([i, f"{sv:.10g}", f"{sv * sv:.10g}", f"{e[i - 1]:.10f}", f"{sp[i - 2]:.10f}" if i >= 2 else ""])
    grafico_varianza(s, args.umbral, lsi.elegir_k(s, args.umbral, "energia"),
                     lsi.elegir_k(s, args.umbral, "sin_primera"), INFORME / "lsi_varianza_explicada.png",
                     f"modo {args.modo}, IDF {args.idf}, N = {corpus.n}, |V| = {len(tf.vocabulario)}")
    print("-> informe/lsi_varianza.csv, informe/lsi_varianza_explicada.png")


if __name__ == "__main__":
    main()
