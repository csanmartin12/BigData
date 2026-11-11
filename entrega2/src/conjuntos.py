"""Arma los dos conjuntos de validación (cortas y documentos) para cada espacio (Fase 4b)."""
from __future__ import annotations

import csv

import numpy as np

from config import ENTREGA2_DIR
from corpus import leer_headers_mongo
from espacios import ESPACIOS, vector_consulta
from indice import Indice
from validacion import Consultas, Espacio, consultas_cortas, conjunto_documentos, muestra_validacion


def preparar(ix: Indice, espacios: dict[str, Espacio], guardar_csv: bool = True) -> tuple[dict, list[dict], dict]:
    """``({espacio: {"cortas": Consultas, "documentos": Consultas}}, consultas_cortas, estadísticas)``."""
    docs = leer_headers_mongo()
    if [d for d, _ in docs] != ix.ids:
        raise RuntimeError("los _id de MongoDB no coinciden con el índice: reconstruya el índice")
    headers = [h for _, h in docs]
    df = dict(zip(ix.tfidf.vocabulario, ix.tfidf.df.tolist()))
    cortas, est = consultas_cortas(headers, df, len(ix.ids))
    q_tfidf = []
    for c in cortas:
        q, oov = ix.tfidf.vectorizar_consulta(c["tokens"])
        assert q is not None and not oov  # tokens tomados del propio corpus
        q_tfidf.append(q)
    muestra = muestra_validacion(len(ix.ids))
    conjuntos = {}
    for e in ESPACIOS:
        vec = np.vstack([vector_consulta(ix, e, q) for q in q_tfidf])
        conjuntos[e] = {"cortas": Consultas("cortas", vec, None),
                        "documentos": conjunto_documentos(espacios[e], muestra)}
    if guardar_csv:
        with open(ENTREGA2_DIR / "informe" / "consultas_cortas.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["n", "consulta", "tokens", "largo_pedido", "llave_origen", "arcfile_origen"])
            for i, c in enumerate(cortas, 1):
                w.writerow([i, c["texto"], len(c["tokens"]), c["largo_pedido"], c["llave"], ix.ids[c["doc_origen"]]])
    return conjuntos, cortas, est
