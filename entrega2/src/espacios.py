"""Espacios vectoriales de búsqueda (TF-IDF y LSI) como matrices densas con filas de norma 1.

- ``tfidf``: las filas de la matriz TF-IDF (ya tienen norma L2 = 1).
- ``lsi``: los vectores ``Σ_k⁻¹ U_kᵀ d`` normalizados con L2. El coseno no cambia con la escala;
  normalizar permite que el coseno sea un producto punto y que K-Means (euclídeo) agrupe según
  el coseno: ‖a − b‖² = 2 − 2·cos(a, b) para vectores unitarios.

Las consultas se vectorizan con la misma transformación y también se normalizan.
"""
from __future__ import annotations

import numpy as np

from indice import Indice
from validacion import Espacio, normalizar_filas

ESPACIOS = ("tfidf", "lsi")


def espacios_desde_indice(ix: Indice, espacios: tuple[str, ...] = ESPACIOS) -> dict[str, Espacio]:
    out = {}
    if "tfidf" in espacios:
        out["tfidf"] = Espacio("tfidf", normalizar_filas(ix.tfidf.matriz.toarray()))
    if "lsi" in espacios:
        out["lsi"] = Espacio("lsi", normalizar_filas(ix.lsi.docs_k))
    return out


def vector_consulta(ix: Indice, espacio: str, q_tfidf: np.ndarray | None) -> np.ndarray | None:
    """Vector de consulta con norma 1 en el espacio pedido (None si la consulta no tiene términos)."""
    if q_tfidf is None:
        return None
    q = q_tfidf if espacio == "tfidf" else ix.lsi.proyectar_consulta(q_tfidf)
    n = float(np.sqrt(np.dot(q, q)))
    return None if n == 0 else q / n
