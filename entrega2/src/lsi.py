"""LSI sobre la matriz TF-IDF, con el truncamiento y la proyección escritos a mano.

- Matriz de entrada: ``A`` = TF-IDF **términos × documentos** (la transpuesta de la CSR de
  ``tfidf.py``), densa.
- SVD con función base: ``numpy.linalg.svd(A, full_matrices=False)`` → ``A = U Σ Vᵀ``. Se usa
  la SVD completa (no ``svds``) porque para elegir k hacen falta **todos** los valores
  singulares.
- Truncamiento a rango k (a mano): ``U_k = U[:, :k]``, ``Σ_k = diag(σ_1..σ_k)``,
  ``V_k = Vᵀ[:k, :]ᵀ``.
- **Misma transformación para documentos y consultas**: ``x_k = Σ_k⁻¹ U_kᵀ x``, con *x* un
  vector TF-IDF en el espacio de términos.
  * Documentos: se aplica a cada columna de A. Como ``U_kᵀ A = Σ_k V_kᵀ``, el resultado es
    exactamente ``V_k`` (fila *j* = documento *j*); se calcula con la fórmula y se comprueba
    que coincide con ``V_k``.
  * Consultas: ``q_k = Σ_k⁻¹ U_kᵀ q``, con q el vector TF-IDF normalizado de la consulta.
- Elección de k (objetiva: no usa las consultas A–E), con el menor k que alcanza el umbral
  (90 % por defecto) según uno de dos criterios:
  * ``energia``: ``Σ_{i≤k} σ_i² / Σ_i σ_i²`` (σ² acumulada / σ² total, tal cual).
  * ``sin_primera`` (por defecto): lo mismo pero **sin la primera componente**,
    ``Σ_{2≤i≤k} σ_i² / Σ_{i≥2} σ_i²``. La primera componente se conserva en el modelo (k la
    incluye), pero no cuenta para el criterio. Motivo: la matriz TF-IDF no está centrada y su
    primera dirección singular es la dirección media del corpus (en este corpus σ₁² es el
    80,2 % de Σσ², y la energía del vector medio es el 78,8 %). Con ``energia`` el 90 % se
    alcanza con k = 2, lo que mide "parecerse al header promedio" y no la variación entre
    documentos.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

UMBRAL_POR_DEFECTO = 0.90
CRITERIOS = ("sin_primera", "energia")
CRITERIO_POR_DEFECTO = "sin_primera"


def svd(a_terminos_docs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """SVD reducida con función base: ``U (m×r)``, ``s (r)`` descendente, ``Vt (r×n)``."""
    return np.linalg.svd(a_terminos_docs, full_matrices=False)


def varianza_explicada_acumulada(s: np.ndarray) -> np.ndarray:
    s2 = s.astype(np.float64) ** 2
    return np.cumsum(s2) / s2.sum()


def varianza_sin_primera_acumulada(s: np.ndarray) -> np.ndarray:
    """Posición j (0-based) = fracción de Σ_{i≥2} σ_i² explicada por σ_2..σ_{j+2}."""
    return varianza_explicada_acumulada(s[1:])


def elegir_k(s: np.ndarray, umbral: float = UMBRAL_POR_DEFECTO, criterio: str = "energia") -> int:
    """Menor k que alcanza ``umbral`` según ``criterio`` (``energia`` o ``sin_primera``)."""
    if criterio == "energia":
        return int(np.searchsorted(varianza_explicada_acumulada(s), umbral - 1e-12) + 1)
    if criterio == "sin_primera":
        return int(np.searchsorted(varianza_sin_primera_acumulada(s), umbral - 1e-12) + 2)
    raise ValueError(f"criterio desconocido: {criterio!r} (opciones: {CRITERIOS})")


def rango_numerico(s: np.ndarray, forma: tuple[int, int]) -> int:
    """Número de σ > tolerancia (misma tolerancia que ``numpy.linalg.matrix_rank``)."""
    tol = s.max() * max(forma) * np.finfo(s.dtype).eps if s.size else 0.0
    return int((s > tol).sum())


def truncar(u: np.ndarray, s: np.ndarray, vt: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(U_k, σ_k, V_k)`` con ``V_k`` de forma documentos × k."""
    if not 1 <= k <= s.size:
        raise ValueError(f"k = {k} fuera de [1, {s.size}]")
    return u[:, :k], s[:k], vt[:k, :].T


def proyectar(u_k: np.ndarray, s_k: np.ndarray, x: np.ndarray) -> np.ndarray:
    """``Σ_k⁻¹ U_kᵀ x`` para vectores en el espacio de términos.

    ``x`` puede ser un vector (|V|) o una matriz con un vector por **fila** (n × |V|); en ese caso
    devuelve n × k (fila i = Σ_k⁻¹ U_kᵀ x_i).
    """
    if np.any(s_k <= 0):
        raise ValueError("Σ_k tiene valores singulares nulos: elija un k ≤ rango")
    return (x @ u_k) / s_k


def reconstruir(u_k: np.ndarray, s_k: np.ndarray, v_k: np.ndarray) -> np.ndarray:
    """``U_k Σ_k V_kᵀ`` (términos × documentos)."""
    return (u_k * s_k) @ v_k.T


@dataclass
class ModeloLSI:
    u_k: np.ndarray       # términos × k
    s_k: np.ndarray       # k
    docs_k: np.ndarray    # documentos × k  (= Σ_k⁻¹ U_kᵀ d_j = V_k)
    s_todos: np.ndarray   # todos los valores singulares (para la curva de varianza)
    k: int
    umbral: float
    criterio: str = CRITERIO_POR_DEFECTO

    @property
    def varianza_k(self) -> float:
        """σ² acumulada / σ² total en k (criterio ``energia``)."""
        return float(varianza_explicada_acumulada(self.s_todos)[self.k - 1])

    @property
    def varianza_sin_primera_k(self) -> float:
        return float(varianza_sin_primera_acumulada(self.s_todos)[self.k - 2]) if self.k >= 2 else 0.0

    def proyectar_consulta(self, q: np.ndarray) -> np.ndarray:
        return proyectar(self.u_k, self.s_k, q)


def ajustar(x_docs_terminos, umbral: float = UMBRAL_POR_DEFECTO, k: int | None = None,
            usv: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
            criterio: str = CRITERIO_POR_DEFECTO) -> tuple[ModeloLSI, dict]:
    """LSI a partir de la matriz TF-IDF documentos × términos (CSR o densa).

    ``usv`` permite pasar la SVD de ``Xᵀ`` ya calculada. Devuelve el modelo y un dict de
    verificaciones numéricas (docs proyectados vs V_k).
    """
    x = x_docs_terminos.toarray() if hasattr(x_docs_terminos, "toarray") else np.asarray(x_docs_terminos)
    a = x.T  # términos × documentos
    u, s, vt = usv if usv is not None else svd(a)
    k = k if k is not None else elegir_k(s, umbral, criterio)
    u_k, s_k, v_k = truncar(u, s, vt, k)
    docs_k = proyectar(u_k, s_k, x)  # misma transformación que las consultas
    chequeo = {
        "max_abs_docs_k_menos_V_k": float(np.abs(docs_k - v_k).max()),
        "rango_numerico": rango_numerico(s, a.shape),
    }
    return ModeloLSI(u_k, s_k, docs_k, s, k, umbral, criterio), chequeo
