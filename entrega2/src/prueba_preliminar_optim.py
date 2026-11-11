"""Prueba preliminar de las 6 configuraciones (todavía NO es el benchmark).

{tfidf, lsi} × {ninguna, kmeans, lsh} × consultas A–E, usando el mismo motor que la CLI
(``buscador.Buscador``):

- Top-5 con los metadatos que deciden la relevancia y la marca según los criterios oficiales.
- Recall relativo top-10 de las 4 configuraciones optimizadas frente a su línea base exhaustiva
  (mismo modelo, ``optim = ninguna``): estricto (intersección de ``_id`` con desempate por
  ``_id``) y con tolerancia a empates (coseno exacto ≥ coseno del 10.º de la línea base). La
  tabla oficial usa el con tolerancia (METODOLOGIA.md, Fase 4).
- Memoria residente (RSS) del proceso de búsqueda con todos los índices cargados.

Salidas: ``informe/prueba_preliminar_optim_top5.csv``/``.md``,
``informe/prueba_preliminar_optim_recall.csv`` y ``informe/memoria_busqueda.json``.

Uso:
    python src/prueba_preliminar_optim.py
"""
from __future__ import annotations

import csv
import json
import resource
import time

import numpy as np

from buscador import MODELOS, OPTIMIZACIONES, Buscador
from config import ENTREGA2_DIR
from consultas import ARGUMENTOS_CLI, CAMPOS_RELEVANCIA, CONSULTAS
from validacion import TOL_EMPATE

INFORME = ENTREGA2_DIR / "informe"
CORTOS = {"ESO DPR TYPE": "DPR TYPE", "DATE-OBS": "DATE-OBS", "ESO INS FILT1 NAME": "FILT1 NAME",
          "ESO DET EXP TYPE": "DET EXP TYPE", "ESO INS OPTI3 NAME": "OPTI3 NAME"}
ARGUMENTOS = ARGUMENTOS_CLI


def memoria() -> dict:
    estado = {}
    with open("/proc/self/status") as f:
        for linea in f:
            if linea.startswith(("VmRSS", "VmHWM")):
                k, v = linea.split(":")
                estado[k] = int(v.split()[0]) / 1024  # MiB
    return {"rss_mib": round(estado["VmRSS"], 1), "pico_rss_mib": round(estado["VmHWM"], 1),
            "ru_maxrss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}


def tamano_estructuras(b: Buscador) -> dict:
    mb = lambda *arrs: round(sum(a.nbytes for a in arrs) / 2**20, 2)  # noqa: E731
    tf = b.ix.tfidf.matriz
    return {"tfidf_csr": mb(tf.data, tf.indices, tf.indptr),
            "espacios_densos_normalizados": {e: mb(x.x) for e, x in b.espacios.items()},
            "lsi_U_k_y_docs_k": mb(b.ix.lsi.u_k, b.ix.lsi.docs_k),
            "kmeans": {e: mb(k.centroides, k.asignacion, k.inverso_indptr, k.inverso_docs) for e, k in b.kmeans.items()},
            "lsh": {e: mb(l.hiperplanos, l.firmas, *[v for t in l.buckets for v in t.values()]) for e, l in b.lsh.items()}}


def main() -> None:
    m0 = memoria()
    t0 = time.perf_counter()
    b = Buscador()
    t_carga = time.perf_counter() - t0
    m1 = memoria()

    # 1) Solo búsquedas (lo que hace el proceso de búsqueda), y su memoria
    salidas, tiempos = {}, {}
    for modelo in MODELOS:
        for optim in OPTIMIZACIONES:
            for cid, kw in ARGUMENTOS.items():
                t0 = time.perf_counter()
                salidas[(modelo, optim, cid)] = b.buscar(modelo=modelo, optim=optim, top=10, **kw)
                tiempos[(modelo, optim, cid)] = 1000 * (time.perf_counter() - t0)
    m2 = memoria()

    # 2) Evaluación (headers para marcar relevancia: es del script de prueba, no del buscador)
    headers = {d["_id"]: d["header"] for d in b.col.find({}, {"header": 1})}
    filas, recall = [], []
    for modelo in MODELOS:
        for optim in OPTIMIZACIONES:
            for cid in ARGUMENTOS:
                r, ms = salidas[(modelo, optim, cid)], tiempos[(modelo, optim, cid)]
                for rango, x in enumerate(r.resultados[:5], 1):
                    h = headers[x["arcfile"]]
                    filas.append({"modelo": modelo, "optim": optim, "consulta": cid, "rango": rango,
                                  "arcfile": x["arcfile"],
                                  "coseno": "" if x["puntaje"] is None else round(x["puntaje"], 4),
                                  **{CORTOS[k]: h.get(k, "—") for k in CAMPOS_RELEVANCIA},
                                  "relevante": CONSULTAS[cid].es_relevante(h)})
                if not r.resultados:
                    filas.append({"modelo": modelo, "optim": optim, "consulta": cid, "rango": "", "arcfile": "(vacío)",
                                  "coseno": "", **{CORTOS[k]: "" for k in CAMPOS_RELEVANCIA}, "relevante": "",
                                  "aviso": " | ".join(r.avisos)})
                rel5 = sum(CONSULTAS[cid].es_relevante(headers[x["arcfile"]]) for x in r.resultados[:5])
                print(f"{modelo:<5} {optim:<7} {cid}: {len(r.resultados):>3} resultados, relevantes en top-5 {rel5}/"
                      f"{min(5, len(r.resultados))}, examinados {r.n_examinados}, {ms:.1f} ms"
                      + (f"  AVISO: {r.avisos[0][:90]}" if r.avisos else ""))

    for modelo in MODELOS:
        for optim in ("kmeans", "lsh"):
            for cid in "ABCD":
                base = salidas[(modelo, "ninguna", cid)].resultados[:10]
                opt = salidas[(modelo, optim, cid)].resultados[:10]
                ids_b = {x["arcfile"] for x in base}
                estricto = len(ids_b & {x["arcfile"] for x in opt}) / len(base)
                umbral = base[-1]["puntaje"] - TOL_EMPATE
                tolerante = min(sum(x["puntaje"] >= umbral for x in opt), len(base)) / len(base)
                recall.append({"modelo": modelo, "optim": optim, "consulta": cid, "recall_estricto": estricto,
                               "recall_tolerante": tolerante, "resultados": len(opt),
                               "examinados": salidas[(modelo, optim, cid)].n_examinados,
                               "examinados_linea_base": salidas[(modelo, "ninguna", cid)].n_examinados,
                               "puntaje_10_linea_base": round(base[-1]["puntaje"], 6),
                               "empatados_en_puntaje_10_linea_base": sum(
                                   abs(x["puntaje"] - base[-1]["puntaje"]) <= TOL_EMPATE for x in base)})
    e_listas = {k: [x["arcfile"] for x in v.resultados] for k, v in salidas.items() if k[2] == "E"}
    e_iguales = len({tuple(v) for v in e_listas.values()}) == 1

    mem = {"antes_de_cargar": m0, "despues_de_cargar_indices": m1, "despues_de_las_30_consultas": m2,
           "nota": "RSS del proceso de búsqueda (Buscador + 30 consultas); los headers para marcar relevancia "
                   "se cargan después de medir",
           "segundos_carga": round(t_carga, 2), "estructuras_mib": tamano_estructuras(b)}
    b.cerrar()

    for nombre, datos in (("prueba_preliminar_optim_top5.csv", filas), ("prueba_preliminar_optim_recall.csv", recall)):
        campos = list(dict.fromkeys(k for f in datos for k in f))
        with open(INFORME / nombre, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            w.writerows(datos)
    with open(INFORME / "prueba_preliminar_optim_top5.md", "w", encoding="utf-8") as fh:
        cols = ["modelo", "optim", "consulta", "rango", "arcfile", "coseno", *CORTOS.values(), "relevante"]
        fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for f in filas:
            fh.write("| " + " | ".join("✔" if f.get(c) is True else "✘" if f.get(c) is False else str(f.get(c, ""))
                                       for c in cols) + " |\n")
    (INFORME / "memoria_busqueda.json").write_text(json.dumps(mem, indent=2, ensure_ascii=False))

    print("\nRecall relativo top-10 frente a la línea base exhaustiva del mismo modelo:")
    for r_ in recall:
        print(f"  {r_['modelo']:<5} {r_['optim']:<6} {r_['consulta']}: tolerante {r_['recall_tolerante']:.1f} "
              f"estricto {r_['recall_estricto']:.1f} | resultados {r_['resultados']} | examinados {r_['examinados']} "
              f"de {r_['examinados_linea_base']} | empatados en el 10.º de la base: {r_['empatados_en_puntaje_10_linea_base']}")
    print(f"Consulta E (solo numérica): mismas {len(next(iter(e_listas.values())))} rutas en las 6 configuraciones: {e_iguales}")
    print(f"Memoria: {json.dumps(mem, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
