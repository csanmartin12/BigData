"""TF-IDF implementado a mano (sin sklearn): vocabulario, df, IDF, TF, normalización L2.

- Vocabulario: términos distintos del corpus en orden alfabético (índice de columna estable).
- df(t): número de documentos que contienen t.
- IDF suavizado (por defecto): ``idf(t) = ln((1 + N) / (1 + df(t))) + 1``.
  IDF clásico (opcional):     ``idf(t) = ln(N / df(t))`` (un término presente en todos los
  documentos pesa 0).
- TF: conteo crudo de t en el documento.
- Peso ``w(t, d) = tf(t, d) · idf(t)``; cada vector de documento se divide por su norma L2.
- Matriz dispersa ``scipy.sparse.csr_matrix`` de documentos × términos; scipy se usa solo para
  almacenar, todos los cálculos están escritos aquí.
- Consulta: se tokeniza con la misma función, se vectoriza con el mismo vocabulario e IDF, y
  los tokens fuera del vocabulario se informan y se ignoran. Si el vector queda con norma 0,
  se devuelve ``None`` con un aviso, no un error.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy import sparse

VARIANTES_IDF = ("suavizado", "clasico")


def construir_vocabulario(docs_tokens: list[list[str]]) -> list[str]:
    return sorted({t for doc in docs_tokens for t in doc})


def calcular_df(docs_tokens: list[list[str]], indice: dict[str, int]) -> np.ndarray:
    df = np.zeros(len(indice), dtype=np.int64)
    for doc in docs_tokens:
        for t in set(doc):
            df[indice[t]] += 1
    return df


def calcular_idf(df: np.ndarray, n_docs: int, variante: str = "suavizado") -> np.ndarray:
    if variante == "suavizado":
        return np.array([math.log((1 + n_docs) / (1 + d)) + 1 for d in df], dtype=np.float64)
    if variante == "clasico":
        if np.any(df == 0):
            raise ValueError("IDF clásico indefinido para términos con df = 0")
        return np.array([math.log(n_docs / d) for d in df], dtype=np.float64)
    raise ValueError(f"variante de IDF desconocida: {variante!r} (opciones: {VARIANTES_IDF})")


def idf_de_termino(df: int, n_docs: int, variante: str = "suavizado") -> float | None:
    """IDF de un término cualquiera, incluso fuera del vocabulario (clásico con df = 0 → None)."""
    if variante == "suavizado":
        return math.log((1 + n_docs) / (1 + df)) + 1
    return math.log(n_docs / df) if df > 0 else None


def matriz_tfidf(docs_tokens: list[list[str]], indice: dict[str, int], idf: np.ndarray) -> sparse.csr_matrix:
    """CSR (documentos × términos) con ``tf · idf`` normalizado por L2 fila a fila."""
    indptr = [0]
    columnas: list[int] = []
    valores: list[float] = []
    for doc in docs_tokens:
        conteos = sorted((indice[t], tf) for t, tf in Counter(doc).items())  # columnas en orden
        cols = [c for c, _ in conteos]
        pesos = [tf * idf[c] for c, tf in conteos]
        norma = math.sqrt(sum(w * w for w in pesos))
        if norma > 0:
            pesos = [w / norma for w in pesos]
        columnas.extend(cols)
        valores.extend(pesos)
        indptr.append(len(columnas))
    return sparse.csr_matrix(
        (np.array(valores, dtype=np.float64), np.array(columnas, dtype=np.int64), np.array(indptr, dtype=np.int64)),
        shape=(len(docs_tokens), len(indice)),
    )


@dataclass
class ModeloTFIDF:
    vocabulario: list[str]
    df: np.ndarray
    idf: np.ndarray
    matriz: sparse.csr_matrix  # documentos × términos, filas con norma L2 = 1
    n_docs: int
    variante: str = "suavizado"

    def __post_init__(self):
        self.indice = {t: i for i, t in enumerate(self.vocabulario)}

    def vectorizar_consulta(self, tokens: list[str]) -> tuple[np.ndarray | None, list[str]]:
        """``(vector denso de largo |V| con norma 1, tokens fuera del vocabulario)``.

        Devuelve ``(None, oov)`` si ningún token de la consulta está en el vocabulario o si todos
        pesan 0 (IDF clásico con df = N).
        """
        oov = [t for t in tokens if t not in self.indice]
        q = np.zeros(len(self.vocabulario), dtype=np.float64)
        for t, tf in Counter(t for t in tokens if t in self.indice).items():
            q[self.indice[t]] = tf * self.idf[self.indice[t]]
        norma = math.sqrt(float(np.dot(q, q)))
        if norma == 0:
            return None, oov
        return q / norma, oov


def ajustar(docs_tokens: list[list[str]], variante: str = "suavizado") -> ModeloTFIDF:
    vocabulario = construir_vocabulario(docs_tokens)
    indice = {t: i for i, t in enumerate(vocabulario)}
    df = calcular_df(docs_tokens, indice)
    idf = calcular_idf(df, len(docs_tokens), variante)
    return ModeloTFIDF(vocabulario, df, idf, matriz_tfidf(docs_tokens, indice, idf), len(docs_tokens), variante)
