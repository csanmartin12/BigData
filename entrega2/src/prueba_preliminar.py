"""Prueba preliminar (todavía NO es el benchmark): top 5 de las consultas A–D con TF-IDF y LSI.

- Índice cargado desde ``entrega2/indice/`` (con verificación de SHA-256).
- Búsqueda exhaustiva por coseno (``similitud.py``). La consulta A es híbrida: MongoDB resuelve
  el filtro de fecha (índice ``date_obs``, día 2026-09-05) y la similitud se calcula solo
  sobre esos candidatos.
- Junto a cada resultado se muestran los metadatos que deciden la relevancia y si el documento
  es relevante según los criterios oficiales (Fase 0).
- Sensibilidad a k (análisis posterior, **no** se usa para elegir k): P@5, P@10 y
  R-precisión para k = criterio literal (energía 90 %) y ``sin_primera`` al 80 / 90 / 95 %.

Salidas: ``informe/prueba_preliminar_top5.csv`` / ``.md`` y ``informe/sensibilidad_k.csv``.

Uso:
    python src/prueba_preliminar.py
"""
from __future__ import annotations

import csv

import numpy as np
from pymongo import MongoClient

import lsi
from config import ENTREGA2_DIR, MONGO_COLECCION, MONGO_DB, MONGO_URI
from consultas import CAMPOS_RELEVANCIA, CONSULTAS
from indice import cargar
from similitud import buscar, cosenos, normas_filas, top_k
from tokenizer import tokenizar

INFORME = ENTREGA2_DIR / "informe"
CORTOS = {"ESO DPR TYPE": "DPR TYPE", "DATE-OBS": "DATE-OBS", "ESO INS FILT1 NAME": "FILT1 NAME",
          "ESO DET EXP TYPE": "DET EXP TYPE", "ESO INS OPTI3 NAME": "OPTI3 NAME"}


def candidatos_mongo(col, consulta, posicion: dict[str, int]) -> np.ndarray | None:
    if consulta.filtro_mongo is None:
        return None
    return np.array(sorted(posicion[d["_id"]] for d in col.find(consulta.filtro_mongo, {"_id": 1})), dtype=np.int64)


def metricas(ranking: list[str], relevantes: set[str]) -> dict:
    r = len(relevantes)
    rel = [i in relevantes for i in ranking]
    return {"P@5": sum(rel[:5]) / 5, "P@10": sum(rel[:10]) / 10,
            "R-prec": (sum(rel[:r]) / r) if r else float("nan"), "|R|": r}


def main() -> None:
    ix = cargar()
    ids, tf, modelo = ix.ids, ix.tfidf, ix.lsi
    posicion = {d: i for i, d in enumerate(ids)}
    with MongoClient(MONGO_URI) as c:
        col = c[MONGO_DB][MONGO_COLECCION]
        headers = {d["_id"]: d["header"] for d in col.find({}, {"header": 1})}
        cands = {cid: candidatos_mongo(col, q, posicion) for cid, q in CONSULTAS.items() if cid != "E"}
    print(f"Índice: modo {ix.manifiesto['modo_campos']}, N = {len(ids)}, |V| = {len(tf.vocabulario)}, "
          f"k = {modelo.k} ({modelo.varianza_k:.1%} de varianza)")

    normas_tf = normas_filas(tf.matriz)
    normas_lsi = normas_filas(modelo.docs_k)
    filas = []
    for cid in "ABCD":
        q_def = CONSULTAS[cid]
        tokens = tokenizar(q_def.texto)
        q, oov = tf.vectorizar_consulta(tokens)
        candidatos = cands[cid]
        univ = set(ids) if candidatos is None else {ids[i] for i in candidatos}
        n_rel = sum(q_def.es_relevante(headers[d]) for d in univ)
        print(f"\nConsulta {cid} '{q_def.texto}' -> tokens {tokens}; fuera del vocabulario: {oov or 'ninguno'}; "
              f"candidatos {'todos' if candidatos is None else len(candidatos)} (relevantes entre ellos: {n_rel})")
        q_k = modelo.proyectar_consulta(q) if q is not None else None
        for metodo, m, qq, normas in (("TF-IDF", tf.matriz, q, normas_tf), ("LSI", modelo.docs_k, q_k, normas_lsi)):
            for rango, (d, p) in enumerate(buscar(m, qq, ids, 5, candidatos, normas), 1):
                h = headers[d]
                fila = {"consulta": cid, "metodo": metodo, "rango": rango, "arcfile": d, "coseno": round(p, 4),
                        **{CORTOS[k]: h.get(k, "—") for k in CAMPOS_RELEVANCIA},
                        "relevante": q_def.es_relevante(h)}
                filas.append(fila)
                print(f"  {metodo:<6} {rango} {d}  cos={p:.4f}  " +
                      "  ".join(f"{CORTOS[k]}={h.get(k, '—')}" for k in CAMPOS_RELEVANCIA) +
                      f"  {'RELEVANTE' if fila['relevante'] else 'no relevante'}")

    with open(INFORME / "prueba_preliminar_top5.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    with open(INFORME / "prueba_preliminar_top5.md", "w", encoding="utf-8") as fh:
        cols = list(filas[0])
        fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for f in filas:
            fh.write("| " + " | ".join("✔" if v is True else "✘" if v is False else str(v) for v in f.values()) + " |\n")
    print("\n-> informe/prueba_preliminar_top5.csv, informe/prueba_preliminar_top5.md")

    # ---- Sensibilidad a k (posterior a la elección; no la modifica) ----
    a = tf.matriz.toarray().T
    u, s, vt = lsi.svd(a)
    ks = sorted({lsi.elegir_k(s, 0.90, "energia"), lsi.elegir_k(s, 0.80, "sin_primera"),
                 lsi.elegir_k(s, 0.90, "sin_primera"), lsi.elegir_k(s, 0.95, "sin_primera")})
    sens = []
    for cid in "ABCD":
        q_def = CONSULTAS[cid]
        q, _ = tf.vectorizar_consulta(tokenizar(q_def.texto))
        candidatos = cands[cid]
        univ = ids if candidatos is None else [ids[i] for i in candidatos]
        relevantes = {d for d in univ if q_def.es_relevante(headers[d])}
        n_buscar = max(len(relevantes), 10)
        rk = [d for d, _ in buscar(tf.matriz, q, ids, n_buscar, candidatos, normas_tf)]
        sens.append({"consulta": cid, "metodo": "TF-IDF", "k": "", "varianza": "", **metricas(rk, relevantes)})
        for k in ks:
            u_k, s_k, _ = lsi.truncar(u, s, vt, k)
            docs_k = lsi.proyectar(u_k, s_k, a.T)
            punt = cosenos(docs_k, lsi.proyectar(u_k, s_k, q))
            rk = [d for d, _ in top_k(punt, ids, n_buscar, candidatos)]
            sens.append({"consulta": cid, "metodo": "LSI", "k": k,
                         "varianza": round(float(lsi.varianza_explicada_acumulada(s)[k - 1]), 4),
                         **metricas(rk, relevantes)})
    with open(INFORME / "sensibilidad_k.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sens[0]))
        w.writeheader()
        w.writerows(sens)
    print(f"Sensibilidad (k = {ks}, k elegido = {modelo.k}):")
    for r in sens:
        print(f"  {r['consulta']} {r['metodo']:<6} k={r['k']!s:<5} P@5={r['P@5']:.2f} P@10={r['P@10']:.2f} "
              f"R-prec={r['R-prec']:.3f} |R|={r['|R|']}")
    print("-> informe/sensibilidad_k.csv")


if __name__ == "__main__":
    main()
