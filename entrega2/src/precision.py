"""Precisión del benchmark (Fase 6, F): P@5 y recall relativo top-10 sobre A–E. Sin repeticiones.

- **P@5** de TF-IDF y LSI exhaustivas × A–E. ``informe/p_at_5_revision.csv`` trae los 5
  resultados con los metadatos que deciden la relevancia, ``relevante_auto`` (criterio de
  ``consultas.py``) y ``relevante_manual``, que llena el usuario. Al volver a correr se
  conservan los valores manuales. P@5 usa ``relevante_manual`` si está completa para esa
  consulta y modelo; si no, usa ``relevante_auto`` y lo marca.
- **Recall relativo top-10** (con tolerancia a empates, oficial, y estricto) de las 4
  configuraciones optimizadas frente a su exhaustiva, en A–E, con los documentos examinados.
  Filas de referencia sin cronometrar:
  - K-Means con n_probe = 2;
  - LSH elegido con documentos completos (b = 16), reconstruido en memoria con la misma
    semilla y verificado contra ``informe/validacion_v2_lsh.csv``.
- Recall y costo de validación de cada configuración (consultas cortas y documentos), desde
  ``validacion_v2_*.csv``.
- Verifica que el top-5 de las 6 configuraciones sea idéntico al de
  ``informe/prueba_preliminar_optim_top5.csv``.

Salidas: ``informe/p_at_5_revision.csv``, ``informe/tabla2_p_at_5.{md,csv}`` y
``informe/tabla3_recall.{md,csv}``.

Uso:
    python src/precision.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lsh_indice  # noqa: E402
from buscador import MODELOS, Buscador  # noqa: E402
from config import ENTREGA2_DIR  # noqa: E402
from consultas import ARGUMENTOS_CLI, CONSULTAS  # noqa: E402
from validacion import TOL_EMPATE  # noqa: E402

INFORME = ENTREGA2_DIR / "informe"
CONSULTAS_IDS = tuple("ABCDE")
TOP = 10
CAMPOS = {"ESO DPR TYPE": "DPR TYPE", "DATE-OBS": "DATE-OBS", "ESO INS FILT1 NAME": "FILT1 NAME",
          "ESO DET EXP TYPE": "DET EXP TYPE", "ESO INS OPTI3 NAME": "OPTI3 NAME", "RA": "RA", "DEC": "DEC"}
NOMBRE_MODELO = {"tfidf": "TF-IDF", "lsi": "LSI"}
SI = {"1", "si", "sí", "s", "true", "t", "x", "✔", "v", "verdadero"}
NO = {"0", "no", "n", "false", "f", "✘", "falso"}


def leer_manual(valor: str | None) -> bool | None:
    v = (valor or "").strip().lower()
    if v in SI:
        return True
    if v in NO:
        return False
    if v:
        raise ValueError(f"relevante_manual = {valor!r}: use 1/0, sí/no o true/false")
    return None


# ---------------------------------------------------------------------------
# P@5
# ---------------------------------------------------------------------------
def p_at_5(b: Buscador, headers: dict) -> tuple[list[dict], list[dict]]:
    ruta = INFORME / "p_at_5_revision.csv"
    previos = {}
    if ruta.exists():
        for f in csv.DictReader(open(ruta, encoding="utf-8")):
            previos[(f["modelo"], f["consulta"], f["rango"], f["arcfile"])] = f.get("relevante_manual", "")
    filas, tabla = [], []
    for modelo in MODELOS:
        for c in CONSULTAS_IDS:
            r = b.buscar(modelo=modelo, optim="ninguna", top=TOP, **ARGUMENTOS_CLI[c])
            for rango, x in enumerate(r.resultados[:5], 1):
                h = headers[x["arcfile"]]
                clave = (modelo, c, str(rango), x["arcfile"])
                filas.append({"modelo": modelo, "consulta": c, "texto": ARGUMENTOS_CLI[c].get("texto", ""),
                              "criterio": CONSULTAS[c].criterio, "rango": rango, "arcfile": x["arcfile"],
                              "coseno": "" if x["puntaje"] is None else f"{x['puntaje']:.6f}",
                              **{v: h.get(k, "") for k, v in CAMPOS.items()},
                              "relevante_auto": int(CONSULTAS[c].es_relevante(h)),
                              "relevante_manual": previos.get(clave, "")})
            mias = [f for f in filas if f["modelo"] == modelo and f["consulta"] == c]
            auto = sum(f["relevante_auto"] for f in mias) / 5
            manual = [leer_manual(f["relevante_manual"]) for f in mias]
            completa = len(manual) == 5 and all(m is not None for m in manual)
            tabla.append({"modelo": modelo, "consulta": c, "p5_auto": auto,
                          "p5_manual": sum(manual) / 5 if completa else "",
                          "p5": sum(manual) / 5 if completa else auto,
                          "fuente": "manual" if completa else "auto (pendiente de revisión manual)",
                          "discrepancias_auto_manual": sum(m is not None and m != bool(f["relevante_auto"])
                                                           for m, f in zip(manual, mias))})
    huerfanos = set(previos) - {(f["modelo"], f["consulta"], str(f["rango"]), f["arcfile"]) for f in filas}
    if any(previos[k] for k in huerfanos):
        print(f"AVISO: {sum(bool(previos[k]) for k in huerfanos)} marcas manuales ya no corresponden a ningún "
              "resultado (cambió el top-5)")
    return filas, tabla


# ---------------------------------------------------------------------------
# Recall relativo
# ---------------------------------------------------------------------------
def recall(base, opt) -> tuple[float, float]:
    """(con tolerancia, estricto) del top-10 ``opt`` frente al top-10 ``base``."""
    base, opt = base.resultados[:TOP], opt.resultados[:TOP]
    ids_b = {x["arcfile"] for x in base}
    estricto = len(ids_b & {x["arcfile"] for x in opt}) / len(base)
    if base[-1]["puntaje"] is None:  # E: solo numérica, sin puntaje
        return estricto, estricto
    umbral = base[-1]["puntaje"] - TOL_EMPATE
    return min(sum(x["puntaje"] >= umbral for x in opt), len(base)) / len(base), estricto


def lsh_referencia(b: Buscador) -> dict:
    """LSH que se habría elegido con documentos completos, reconstruido en memoria."""
    man = json.loads((ENTREGA2_DIR / "indice" / "manifiesto.json").read_text())["lsh"]
    out = {}
    for e in MODELOS:
        s = man["espacios"][e]["eleccion_con_documentos_secundaria"]
        out[e] = (lsh_indice.construir(e, b.espacios[e].x, s["n_bits"], s["n_tablas"], semilla=man["semilla"],
                                       centrado=s["centrado"], radio_max=s["radio_max"]), s)
    return out


def verificar_referencia(b: Buscador, ref: dict) -> dict:
    """Reproduce el recall y el costo de validación del LSH de referencia (ambos conjuntos)."""
    import conjuntos
    from validacion import evaluar_de, linea_base_de
    conj, _, _ = conjuntos.preparar(b.ix, b.espacios, guardar_csv=False)
    v2 = list(csv.DictReader(open(INFORME / "validacion_v2_lsh.csv", encoding="utf-8")))
    out = {}
    for e, (lsh, s) in ref.items():
        for cj in ("cortas", "documentos"):
            lb = linea_base_de(b.espacios[e], conj[e][cj])
            r = evaluar_de(b.espacios[e], lb, lambda j, q, excl: (lsh.candidatos(q, TOP, excluir=excl)[0], {}))
            fila = next(f for f in v2 if f["espacio"] == e and f["conjunto"] == cj and int(f["n_bits"]) == s["n_bits"]
                        and int(f["n_tablas"]) == s["n_tablas"] and int(f["radio_max"]) == s["radio_max"]
                        and (f["centrado"] == "True") == s["centrado"])
            ok = all(abs(r[k] - float(fila[k])) < 1e-9 for k in ("recall_tolerante", "recall_estricto", "costo"))
            out[(e, cj)] = {"recall_tolerante": r["recall_tolerante"], "recall_estricto": r["recall_estricto"],
                            "costo": r["costo"], "igual_a_validacion_v2": ok}
            if not ok:
                raise RuntimeError(f"LSH de referencia {e}/{cj} no reproduce validacion_v2_lsh.csv: {r} vs {fila}")
    return out


def validacion_de(config: dict) -> dict:
    """Recall y costo de validación (cortas y documentos) desde los CSV del barrido v2."""
    e = config["modelo"]
    out = {}
    if config["optim"] == "kmeans":
        v2 = csv.DictReader(open(INFORME / "validacion_v2_kmeans.csv", encoding="utf-8"))
        filas = [f for f in v2 if f["espacio"] == e and int(f["n_clusteres"]) == config["n_clusteres"]
                 and int(f["n_probe"]) == config["n_probe"]]
    else:
        v2 = csv.DictReader(open(INFORME / "validacion_v2_lsh.csv", encoding="utf-8"))
        filas = [f for f in v2 if f["espacio"] == e and int(f["n_bits"]) == config["n_bits"]
                 and int(f["n_tablas"]) == config["n_tablas"] and int(f["radio_max"]) == config["radio_max"]
                 and (f["centrado"] == "True") == config["centrado"]]
    for f in filas:
        out[f["conjunto"]] = {k: float(f[k]) for k in ("recall_tolerante", "recall_estricto", "costo")}
    return out


def configuraciones(b: Buscador, ref: dict) -> list[dict]:
    man = json.loads((ENTREGA2_DIR / "indice" / "manifiesto.json").read_text())
    out = []
    for e in MODELOS:
        km, lh = man["kmeans"]["espacios"][e], man["lsh"]["espacios"][e]
        out += [
            {"modelo": e, "optim": "kmeans", "referencia": False, "n_clusteres": km["n_clusteres"], "n_probe": 1,
             "etiqueta": f"{NOMBRE_MODELO[e]} + K-Means (c = {km['n_clusteres']}, n_probe = 1)"},
            {"modelo": e, "optim": "lsh", "referencia": False, **{k: lh[k] for k in ("n_bits", "n_tablas", "radio_max",
                                                                                     "centrado")},
             "etiqueta": f"{NOMBRE_MODELO[e]} + LSH (b = {lh['n_bits']}, L = {lh['n_tablas']}, centrado)"},
            {"modelo": e, "optim": "kmeans", "referencia": True, "n_clusteres": km["n_clusteres"], "n_probe": 2,
             "etiqueta": f"{NOMBRE_MODELO[e]} + K-Means (c = {km['n_clusteres']}, n_probe = 2) [ref.]"},
        ]
        s = ref[e][1]
        out.append({"modelo": e, "optim": "lsh", "referencia": True,
                    **{k: s[k] for k in ("n_bits", "n_tablas", "radio_max", "centrado")},
                    "etiqueta": f"{NOMBRE_MODELO[e]} + LSH (b = {s['n_bits']}, L = {s['n_tablas']}, centrado; "
                                "elegido con documentos) [ref.]"})
    return out


def tabla_recall(b: Buscador, ref: dict) -> list[dict]:
    filas = []
    base = {(e, c): b.buscar(modelo=e, optim="ninguna", top=TOP, **ARGUMENTOS_CLI[c]) for e in MODELOS
            for c in CONSULTAS_IDS}
    for cfg in configuraciones(b, ref):
        e = cfg["modelo"]
        original = b.lsh[e]
        if cfg["optim"] == "lsh" and cfg["referencia"]:
            b.lsh[e] = ref[e][0]
        try:
            fila = {"configuracion": cfg["etiqueta"], "modelo": e, "optim": cfg["optim"],
                    "referencia": cfg["referencia"]}
            tol, est = [], []
            for c in CONSULTAS_IDS:
                r = b.buscar(modelo=e, optim=cfg["optim"], top=TOP, n_probe=cfg.get("n_probe", 1), **ARGUMENTOS_CLI[c])
                rt, rs = recall(base[(e, c)], r)
                tol.append(rt)
                est.append(rs)
                fila[f"{c}_tol"], fila[f"{c}_estr"] = rt, rs
                fila[f"{c}_examinados"] = r.n_examinados if r.n_examinados is not None else ""
                fila[f"{c}_candidatos_exhaustiva"] = base[(e, c)].n_examinados or ""
            fila["media_AE_tol"], fila["media_AE_estr"] = sum(tol) / 5, sum(est) / 5
            fila["media_AD_tol"], fila["media_AD_estr"] = sum(tol[:4]) / 4, sum(est[:4]) / 4
            costos = [fila[f"{c}_examinados"] / fila[f"{c}_candidatos_exhaustiva"] for c in "ABCD"]
            fila["costo_medio_AD"] = sum(costos) / 4
            val = validacion_de(cfg)
            for cj in ("cortas", "documentos"):
                for k in ("recall_tolerante", "costo"):
                    fila[f"validacion_{cj}_{k}"] = val.get(cj, {}).get(k, "")
            filas.append(fila)
        finally:
            b.lsh[e] = original
    return filas


# ---------------------------------------------------------------------------
# Verificación contra la prueba preliminar
# ---------------------------------------------------------------------------
def verificar_prueba_preliminar(b: Buscador) -> list[str]:
    previo: dict = {}
    for f in csv.DictReader(open(INFORME / "prueba_preliminar_optim_top5.csv", encoding="utf-8")):
        if f["rango"]:
            previo.setdefault((f["modelo"], f["optim"], f["consulta"]), []).append(f["arcfile"])
    distintos = []
    for (m, o, c), ids in previo.items():
        r = b.buscar(modelo=m, optim=o, top=TOP, **ARGUMENTOS_CLI[c])
        if [x["arcfile"] for x in r.resultados[:5]] != ids:
            distintos.append(f"{m}/{o}/{c}")
    return distintos


# ---------------------------------------------------------------------------
def _f(x, nd=2) -> str:
    return "—" if x == "" or x is None else (f"{x:.{nd}f}".replace(".", ",") if isinstance(x, float) else str(x))


def _csv(ruta: Path, filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for f in filas for k in f)))
        w.writeheader()
        w.writerows(filas)


def main() -> None:
    b = Buscador()
    distintos = verificar_prueba_preliminar(b)
    print("Top-5 idéntico al de la prueba preliminar (30 pares):", "sí" if not distintos else f"NO: {distintos}")
    headers = {d["_id"]: d["header"] for d in b.col.find({}, {"header": 1})}

    filas_rev, p5 = p_at_5(b, headers)
    _csv(INFORME / "p_at_5_revision.csv", filas_rev)
    _csv(INFORME / "tabla2_p_at_5.csv", p5)
    md = ["## Tabla 2 — Precisión P@5 (búsqueda exhaustiva)", "",
          "| Consulta | Texto / filtro | TF-IDF | LSI |", "|---|---|---:|---:|"]
    for c in CONSULTAS_IDS:
        v = {f["modelo"]: f for f in p5 if f["consulta"] == c}
        desc = ARGUMENTOS_CLI[c].get("texto") or "RA [84, 85] × DEC [−70, −69]"
        if c == "A":
            desc += " + DATE-OBS 2026-09-05"
        md.append(f"| {c} | {desc} | {_f(v['tfidf']['p5'])} | {_f(v['lsi']['p5'])} |")
    for etiqueta, sel in (("Promedio A–E", CONSULTAS_IDS), ("Promedio A–D", "ABCD")):
        md.append(f"| **{etiqueta}** | | " + " | ".join(
            f"**{_f(sum(f['p5'] for f in p5 if f['modelo'] == m and f['consulta'] in sel) / len(sel))}**"
            for m in MODELOS) + " |")
    fuentes = {f["fuente"] for f in p5}
    md += ["", f"Fuente de la relevancia: {', '.join(sorted(fuentes))}. Revisión: `informe/p_at_5_revision.csv`.", ""]

    ref = lsh_referencia(b)
    ver = verificar_referencia(b, ref)
    print("LSH de referencia reproduce validacion_v2_lsh.csv:", all(v["igual_a_validacion_v2"] for v in ver.values()))
    rec = tabla_recall(b, ref)
    _csv(INFORME / "tabla3_recall.csv", rec)
    cols = [f for f in rec if not f["referencia"]]
    refs = [f for f in rec if f["referencia"]]
    for titulo, grupo in (("Tabla 3 — Recall relativo top-10 frente a la exhaustiva del mismo modelo "
                           "(con tolerancia / estricto)", cols),
                          ("Tabla 3 (referencia, sin cronometrar) — K-Means n_probe = 2 y LSH elegido con "
                           "documentos completos", refs)):
        md += [f"## {titulo}", "", "| Consulta | " + " | ".join(f["configuracion"] for f in grupo) + " |",
               "|---|" + "---:|" * len(grupo)]
        for c in CONSULTAS_IDS:
            md.append(f"| {c} | " + " | ".join(f"{_f(f[c + '_tol'], 1)} / {_f(f[c + '_estr'], 1)}" for f in grupo) + " |")
        md.append("| **Promedio A–E** | " + " | ".join(
            f"**{_f(f['media_AE_tol'])}** / {_f(f['media_AE_estr'])}" for f in grupo) + " |")
        md.append("| **Promedio A–D** | " + " | ".join(
            f"**{_f(f['media_AD_tol'])}** / {_f(f['media_AD_estr'])}" for f in grupo) + " |")
        md.append("")
    md += ["## Costo (documentos con coseno exacto) y recall de validación", "",
           "| Configuración | Examinados A / B / C / D | Costo medio A–D | Validación cortas: recall / costo | "
           "Validación documentos: recall / costo |", "|---|---|---:|---|---|"]
    for f in rec:
        ex = " / ".join(f"{f[c + '_examinados']} de {f[c + '_candidatos_exhaustiva']}" for c in "ABCD")
        md.append(f"| {f['configuracion']} | {ex} | {_f(f['costo_medio_AD'], 3)} | "
                  f"{_f(f['validacion_cortas_recall_tolerante'], 3)} / {_f(f['validacion_cortas_costo'], 3)} | "
                  f"{_f(f['validacion_documentos_recall_tolerante'], 3)} / {_f(f['validacion_documentos_costo'], 3)} |")
    md += ["", "En E todas las configuraciones resuelven el mismo filtro de MongoDB (sin índice vectorial): "
           "su recall es 1 por construcción.", ""]
    texto = "\n".join(md) + "\n"
    (INFORME / "tabla2_p_at_5.md").write_text(texto.split("## Tabla 3")[0], encoding="utf-8")
    (INFORME / "tabla3_recall.md").write_text("## Tabla 3" + texto.split("## Tabla 3", 1)[1], encoding="utf-8")
    b.cerrar()
    print(texto)


if __name__ == "__main__":
    main()
