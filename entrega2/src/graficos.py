"""Gráficos estáticos (PNG) para el informe, con un solo estilo.

Paleta de referencia de la guía de visualización: superficie ``#fcfcfb``, textos en tinta
(``#0b0b0b`` / ``#52514e``) y nunca en el color de la serie, grilla fina continua, series
categóricas en orden fijo (azul, naranja, aqua, amarillo), líneas de 2 px, marcadores ≥ 8 px con
anillo del color de superficie, leyenda cuando hay ≥ 2 series y etiquetas directas selectivas.
"""
from __future__ import annotations

SUPERFICIE, TINTA, TINTA2, GRILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")


def _ejes(ax, titulo: str, xlabel: str, ylabel: str):
    ax.set_facecolor(SUPERFICIE)
    ax.set_title(titulo, color=TINTA, fontsize=10.5, loc="left")
    ax.set_xlabel(xlabel, color=TINTA2, fontsize=9)
    ax.set_ylabel(ylabel, color=TINTA2, fontsize=9)
    ax.grid(True, color=GRILLA, linewidth=1, linestyle="-")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRILLA)
    ax.tick_params(colors=TINTA2, labelsize=8.5)


def curvas_costo_recall(paneles: list[dict], ruta, umbral: float, titulo: str) -> None:
    """Un panel por espacio. Cada panel: ``{"titulo", "series": [{"nombre", "x", "y", "etiquetas"}],
    "elegido": {"x", "y", "texto"}}``. x = costo (fracción examinada, log), y = recall.

    Solo llevan etiqueta de punto las series que traen ``etiquetas`` (etiquetado selectivo). El
    eje y se ajusta a los datos (es un gráfico de líneas, no de barras), sin pasar de 0 a 1.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter, NullLocator

    todos_y = [y for p in paneles for s in p["series"] for y in s["y"]]
    todos_x = [x for p in paneles for s in p["series"] for x in s["x"]]
    y_min = max(0.0, min(min(todos_y), umbral) - 0.05)
    y_min = float(int(y_min * 20) / 20)  # múltiplo de 0,05 hacia abajo
    candidatos_x = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
    ticks_x = [t for t in candidatos_x if min(todos_x) / 1.6 <= t <= max(todos_x) * 1.6]

    fig, axes = plt.subplots(1, len(paneles), figsize=(5.6 * len(paneles), 4.6), dpi=200, sharey=True)
    axes = [axes] if len(paneles) == 1 else list(axes)
    fig.patch.set_facecolor(SUPERFICIE)
    for ax, panel in zip(axes, paneles):
        _ejes(ax, panel["titulo"], "costo: fracción del corpus examinada (log)",
              "recall relativo top-10 (tolerante a empates)")
        for color, serie in zip(SERIES, panel["series"]):
            ax.plot(serie["x"], serie["y"], color=color, linewidth=2, marker="o", markersize=5,
                    markeredgecolor=SUPERFICIE, markeredgewidth=1.5, label=serie["nombre"], zorder=3)
            e = panel.get("elegido") or {}
            for x, y, et in zip(serie["x"], serie["y"], serie.get("etiquetas", [])):
                if et and not (x == e.get("x") and y == e.get("y")):  # el elegido ya lleva su rótulo
                    ax.annotate(et, (x, y), xytext=(4, -10), textcoords="offset points", color=TINTA2, fontsize=7)
        ax.axhline(umbral, color=TINTA2, linewidth=1, zorder=2)
        ax.text(0.99, umbral - 0.008, f"umbral {umbral:.2f}".replace(".", ","), color=TINTA2, fontsize=8,
                ha="right", va="top", transform=ax.get_yaxis_transform())
        e = panel.get("elegido")
        if e:
            ax.scatter([e["x"]], [e["y"]], s=150, facecolors="none", edgecolors=TINTA, linewidths=1.5, zorder=5)
            ax.annotate(e["texto"], (e["x"], e["y"]), xytext=(10, -18), textcoords="offset points", color=TINTA,
                        fontsize=9, fontweight="bold", va="top")
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(ticks_x))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
        ax.set_xlim(min(todos_x) / 1.4, max(todos_x) * 1.4)
        ax.set_ylim(y_min, 1.01)
        leyenda = ax.legend(loc="lower right", frameon=False, fontsize=8)
        for t in leyenda.get_texts():
            t.set_color(TINTA)
    fig.suptitle(titulo, color=TINTA, fontsize=11.5, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def frontera_pareto(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Puntos no dominados (menor costo x, mayor recall y), ordenados por costo."""
    fx, fy, mejor = [], [], -1.0
    for x, y in sorted(zip(xs, ys), key=lambda t: (t[0], -t[1])):
        if y > mejor + 1e-12:
            fx.append(x)
            fy.append(y)
            mejor = y
    return fx, fy


def nube_costo_recall(paneles: list[dict], ruta, umbral: float, titulo: str) -> None:
    """Muchas configuraciones: nube de puntos por serie + su frontera de Pareto (línea).

    Panel: ``{"titulo", "series": [{"nombre", "x", "y"}], "elegido": {"x", "y", "texto"}}``.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter, NullLocator

    todos_x = [x for p in paneles for s in p["series"] for x in s["x"]]
    todos_y = [y for p in paneles for s in p["series"] for y in s["y"]]
    y_min = float(int(max(0.0, min(min(todos_y), umbral) - 0.05) * 20) / 20)
    candidatos_x = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
    ticks_x = [t for t in candidatos_x if min(todos_x) / 1.6 <= t <= max(todos_x) * 1.6]
    fig, axes = plt.subplots(1, len(paneles), figsize=(5.6 * len(paneles), 4.6), dpi=200, sharey=True)
    axes = [axes] if len(paneles) == 1 else list(axes)
    fig.patch.set_facecolor(SUPERFICIE)
    for ax, panel in zip(axes, paneles):
        _ejes(ax, panel["titulo"], "costo: fracción del corpus rerankeada (log)",
              "recall relativo top-10 (tolerante a empates)")
        for color, serie in zip(SERIES, panel["series"]):
            ax.scatter(serie["x"], serie["y"], s=16, color=color, alpha=0.45, edgecolors="none", zorder=2)
            fx, fy = frontera_pareto(serie["x"], serie["y"])
            ax.plot(fx, fy, color=color, linewidth=2, marker="o", markersize=5, markeredgecolor=SUPERFICIE,
                    markeredgewidth=1.5, label=f"{serie['nombre']} (frontera de Pareto)", zorder=3)
        ax.axhline(umbral, color=TINTA2, linewidth=1, zorder=1)
        ax.text(0.01, umbral + 0.008, f"umbral {umbral:.2f}".replace(".", ","), color=TINTA2, fontsize=8,
                ha="left", va="bottom", transform=ax.get_yaxis_transform())
        e = panel.get("elegido")
        if e:
            ax.scatter([e["x"]], [e["y"]], s=150, facecolors="none", edgecolors=TINTA, linewidths=1.5, zorder=5)
            derecha = e["x"] > (min(todos_x) * max(todos_x)) ** 0.5  # punto en la mitad derecha (escala log)
            ax.annotate(e["texto"], (e["x"], e["y"]), xytext=(-12 if derecha else 10, -18), textcoords="offset points",
                        color=TINTA, fontsize=8.5, fontweight="bold", va="top", ha="right" if derecha else "left")
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(ticks_x))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
        ax.set_xlim(min(todos_x) / 1.4, max(todos_x) * 1.4)
        ax.set_ylim(y_min, 1.01)
        leyenda = ax.legend(loc="lower right", frameon=False, fontsize=8)
        for t in leyenda.get_texts():
            t.set_color(TINTA)
    fig.suptitle(titulo, color=TINTA, fontsize=11.5, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)
