"""Conjuntos de validación y métricas para elegir hiperparámetros (Fases 4 y 4b).

Dos conjuntos (METODOLOGIA.md, "Fase 4b — Revisión del protocolo de validación"):

- **Consultas cortas** (oficial para elegir): 200 consultas de 1–4 tokens tomadas de un par
  llave-valor de texto de un documento al azar (semilla 20261112). El documento de origen no se
  excluye.
- **Documentos completos** (secundario): 200 documentos (semilla 20261111) usados como consulta
  con su propio vector, **excluidos** de sus resultados.

Métricas sobre top-10 frente a la búsqueda exhaustiva en el mismo espacio: recall relativo con
tolerancia a empates (oficial) y estricto; costo = documentos rerankeados con coseno exacto /
(N, o N − 1 si se excluye el documento consulta).

Criterio: menor costo medio con recall con tolerancia medio ≥ 0,90; desempates por
``elegir(..., claves_desempate)``; si nadie llega, el de mayor recall.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SEMILLA_VALIDACION = 20261111
SEMILLA_CORTAS = 20261112
N_VALIDACION = 200
TOP = 10
UMBRAL_RECALL = 0.90
TOL_EMPATE = 1e-12


def muestra_validacion(n_docs: int, n: int = N_VALIDACION, semilla: int = SEMILLA_VALIDACION) -> np.ndarray:
    return np.sort(np.random.default_rng(semilla).choice(n_docs, size=n, replace=False))


def normalizar_filas(m: np.ndarray) -> np.ndarray:
    """L2 por fila (filas de norma 0 quedan en 0)."""
    normas = np.sqrt(np.einsum("ij,ij->i", m, m))
    out = np.zeros_like(m, dtype=np.float64)
    ok = normas > 0
    out[ok] = m[ok] / normas[ok, None]
    return out


def ordenar_top(indices: np.ndarray, puntajes: np.ndarray, k: int = TOP) -> tuple[np.ndarray, np.ndarray]:
    """Top-k por puntaje desc. y, a igual puntaje, índice asc. (= ``_id`` asc.)."""
    if indices.size == 0:
        return indices, puntajes
    orden = np.lexsort((indices, -puntajes))[:k]
    return indices[orden], puntajes[orden]


def recall_estricto(top_opt: np.ndarray, top_base: np.ndarray) -> float:
    return len(set(top_opt.tolist()) & set(top_base.tolist())) / len(top_base)


def recall_tolerante(puntajes_opt: np.ndarray, puntajes_base: np.ndarray, tol: float = TOL_EMPATE) -> float:
    """Aciertos = resultados optimizados con coseno exacto ≥ coseno del último de la línea base."""
    umbral = puntajes_base[-1] - tol
    return min(int((puntajes_opt >= umbral).sum()), len(puntajes_base)) / len(puntajes_base)


# ---------------------------------------------------------------------------
# Consultas cortas
# ---------------------------------------------------------------------------
def consultas_cortas(headers: list[dict], df: dict[str, int], n_docs: int, n: int = N_VALIDACION,
                     semilla: int = SEMILLA_CORTAS, max_intentos: int = 100_000) -> tuple[list[dict], dict]:
    """Genera ``n`` consultas cortas según el protocolo; devuelve (consultas, estadísticas).

    ``headers``: header de cada documento en el orden del corpus. ``df``: df de cada token.
    """
    from tokenizer import tokenizar

    rng = np.random.default_rng(semilla)
    consultas, reemplazadas, motivos = [], 0, {"todos_df_N": 0, "vacia": 0}
    for _ in range(max_intentos):
        if len(consultas) == n:
            break
        d = int(rng.integers(0, n_docs))
        pares = [(k, v) for k, v in headers[d].items() if isinstance(v, str)]
        k, v = pares[int(rng.integers(0, len(pares)))]
        largo = int(rng.integers(1, 5))
        tokens = tokenizar(v, llave=k)[:largo]
        if not tokens:
            reemplazadas += 1
            motivos["vacia"] += 1
            continue
        if all(df.get(t, 0) == n_docs for t in tokens):
            reemplazadas += 1
            motivos["todos_df_N"] += 1
            continue
        consultas.append({"tokens": tokens, "texto": " ".join(tokens), "doc_origen": d, "llave": k,
                          "largo_pedido": largo})
    if len(consultas) < n:
        raise RuntimeError(f"solo se generaron {len(consultas)} consultas cortas en {max_intentos} intentos")
    est = {"generadas": len(consultas), "reemplazadas": reemplazadas, "motivos_reemplazo": motivos,
           "distintas": len({tuple(c["tokens"]) for c in consultas}),
           "largo_medio": float(np.mean([len(c["tokens"]) for c in consultas])),
           "por_largo": {L: sum(len(c["tokens"]) == L for c in consultas) for L in range(1, 5)}}
    return consultas, est


# ---------------------------------------------------------------------------
# Espacios, conjuntos, línea base y evaluación
# ---------------------------------------------------------------------------
@dataclass
class Espacio:
    """Vectores de documentos de un espacio (TF-IDF o LSI) normalizados con L2, como matriz densa."""
    nombre: str
    x: np.ndarray  # N × d, filas con norma 1

    def cosenos(self, q: np.ndarray, sobre: np.ndarray | None = None) -> np.ndarray:
        """Coseno de ``q`` (norma 1) con todas las filas o con las de ``sobre``."""
        return self.x @ q if sobre is None else self.x[sobre] @ q


@dataclass
class Consultas:
    nombre: str
    vectores: np.ndarray                 # n × d, filas con norma 1, en el espacio evaluado
    excluir: np.ndarray | None = None    # documento a excluir por consulta (dejar uno fuera) o None


def conjunto_documentos(esp: Espacio, muestra: np.ndarray) -> Consultas:
    return Consultas("documentos", esp.x[muestra], muestra)


@dataclass
class LineaBase:
    consultas: Consultas
    top: list[np.ndarray] = field(default_factory=list)
    puntajes: list[np.ndarray] = field(default_factory=list)
    # cosenos de cada consulta con TODOS los documentos: el coseno exacto de un candidato es el
    # mismo número, así que la evaluación lo indexa en vez de recalcularlo (no cambia el resultado)
    cosenos_todos: list[np.ndarray] = field(default_factory=list)


def linea_base_de(esp: Espacio, cons: Consultas, k: int = TOP) -> LineaBase:
    lb = LineaBase(cons)
    todos = np.arange(esp.x.shape[0])
    for j, q in enumerate(cons.vectores):
        p = esp.cosenos(q)
        lb.cosenos_todos.append(p)
        if cons.excluir is not None:
            m = todos != cons.excluir[j]
            t, s = ordenar_top(todos[m], p[m], k)
        else:
            t, s = ordenar_top(todos, p, k)
        lb.top.append(t)
        lb.puntajes.append(s)
    return lb


def evaluar_de(esp: Espacio, lb: LineaBase, candidatos_de, k: int = TOP) -> dict:
    """``candidatos_de(j, q, excluir) -> (indices_candidatos, extra)`` para la consulta j.

    El coseno exacto se calcula solo sobre los candidatos (sin el documento excluido, si hay).
    """
    cons = lb.consultas
    n = esp.x.shape[0] - (1 if cons.excluir is not None else 0)
    rec_e, rec_t, costo, n_menos_k = [], [], [], 0
    extras: dict[str, list] = {}
    for j, q in enumerate(cons.vectores):
        excl = None if cons.excluir is None else int(cons.excluir[j])
        cand, extra = candidatos_de(j, q, excl)
        cand = np.asarray(cand, dtype=np.int64)
        if excl is not None:
            cand = cand[cand != excl]
        t, s = ordenar_top(cand, lb.cosenos_todos[j][cand], k)
        rec_e.append(recall_estricto(t, lb.top[j]))
        rec_t.append(recall_tolerante(s, lb.puntajes[j]))
        costo.append(cand.size / n)
        n_menos_k += cand.size < k
        for kk, v in extra.items():
            extras.setdefault(kk, []).append(v)
    return {"recall_tolerante": float(np.mean(rec_t)), "recall_estricto": float(np.mean(rec_e)),
            "recall_tolerante_min": float(np.min(rec_t)), "recall_tolerante_p10": float(np.percentile(rec_t, 10)),
            "costo": float(np.mean(costo)), "costo_max": float(np.max(costo)),
            "consultas_con_menos_de_k": int(n_menos_k),
            **{f"{kk}_medio": float(np.mean(v)) for kk, v in extras.items()}}


# Compatibilidad con la primera validación (documentos completos, dejar uno fuera)
def linea_base(esp: Espacio, consultas: np.ndarray, k: int = TOP) -> LineaBase:
    return linea_base_de(esp, conjunto_documentos(esp, consultas), k)


def evaluar(esp: Espacio, lb: LineaBase, candidatos_de, k: int = TOP) -> dict:
    """Primera validación: ``candidatos_de(i)`` recibe el índice del documento consulta."""
    return evaluar_de(esp, lb, lambda j, q, excl: candidatos_de(lb.consultas.excluir[j]), k)


def elegir(filas: list[dict], clave_memoria: str | tuple[str, ...], umbral: float = UMBRAL_RECALL) -> tuple[dict, str]:
    """Aplica el criterio. ``clave_memoria``: clave(s) de desempate ascendentes tras el recall."""
    claves = (clave_memoria,) if isinstance(clave_memoria, str) else tuple(clave_memoria)
    ok = [f for f in filas if f["recall_tolerante"] >= umbral]
    if ok:
        f = min(ok, key=lambda f: (round(f["costo"], 12), -f["recall_tolerante"], *(f[c] for c in claves)))
        return f, f"menor costo medio con recall tolerante ≥ {umbral:.2f} ({len(ok)} de {len(filas)} cumplen)"
    f = max(filas, key=lambda f: (f["recall_tolerante"], -f["costo"], *(-f[c] for c in claves)))
    return f, f"ninguna configuración llega a {umbral:.2f}: se elige la de mayor recall tolerante (limitación)"
