"""Similitud coseno escrita a mano y búsqueda exhaustiva top-K (línea base del recall relativo).

``cos(u, v) = (u · v) / (‖u‖ ‖v‖)``. Norma 0 (vector vacío): la similitud se define como 0 y
el caso se informa; nunca se divide por cero. La búsqueda exhaustiva compara la consulta con
**todos** los documentos (o con todos los candidatos que deja el filtro de MongoDB) y ordena
por puntaje descendente; los empates se resuelven por posición en el corpus, es decir, por
``_id`` ascendente, para que el resultado sea determinista.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
from scipy import sparse


def coseno(u: np.ndarray, v: np.ndarray) -> float:
    nu, nv = math.sqrt(float(np.dot(u, u))), math.sqrt(float(np.dot(v, v)))
    if nu == 0.0 or nv == 0.0:
        return 0.0
    return float(np.dot(u, v)) / (nu * nv)


def normas_filas(m) -> np.ndarray:
    """‖fila‖₂ de una matriz densa o CSR."""
    if sparse.issparse(m):
        m = m.tocsr()
        cuadrados = np.zeros(m.shape[0])
        for i in range(m.shape[0]):
            datos = m.data[m.indptr[i]:m.indptr[i + 1]]
            cuadrados[i] = float(np.dot(datos, datos))
        return np.sqrt(cuadrados)
    return np.sqrt(np.einsum("ij,ij->i", m, m))


def cosenos(m, q: np.ndarray, normas: np.ndarray | None = None) -> np.ndarray | None:
    """Coseno entre cada fila de ``m`` y ``q``. Filas con norma 0 → 0. ``q`` con norma 0 → None."""
    nq = math.sqrt(float(np.dot(q, q)))
    if nq == 0.0:
        warnings.warn("consulta con norma 0: no hay términos para comparar", stacklevel=2)
        return None
    normas = normas_filas(m) if normas is None else normas
    productos = np.asarray(m @ q).ravel()
    out = np.zeros(m.shape[0])
    ok = normas > 0
    out[ok] = productos[ok] / (normas[ok] * nq)
    return out


def top_k(puntajes: np.ndarray, ids: list[str], k: int, candidatos: np.ndarray | None = None) -> list[tuple[str, float]]:
    """Los ``k`` mejores (``_id``, coseno). ``candidatos`` = índices permitidos (filtro híbrido)."""
    idx = np.arange(len(ids)) if candidatos is None else np.asarray(sorted(candidatos), dtype=np.int64)
    if idx.size == 0:
        return []
    p = puntajes[idx]
    orden = np.lexsort((idx, -p))[:k]  # puntaje desc., luego posición asc. (= _id asc.)
    return [(ids[idx[i]], float(p[i])) for i in orden]


def buscar(m, q: np.ndarray | None, ids: list[str], k: int, candidatos=None, normas=None) -> list[tuple[str, float]]:
    """Búsqueda exhaustiva: ``[]`` si la consulta no tiene términos útiles (norma 0)."""
    if q is None:
        return []
    puntajes = cosenos(m, q, normas)
    return [] if puntajes is None else top_k(puntajes, ids, k, candidatos)
