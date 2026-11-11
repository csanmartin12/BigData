"""Persistencia del índice vectorial en ``entrega2/indice/``.

Archivos:
    vocabulario.json   lista de términos (posición = columna)
    doc_ids.json       ARCFILE de cada fila (orden del corpus = _id ascendente)
    df.npy, idf.npy    df e IDF por término
    tfidf.npz          matriz TF-IDF documentos × términos (scipy.sparse CSR)
    lsi_U_k.npy        U_k (términos × k)
    lsi_sigma_k.npy    σ_1..σ_k
    lsi_docs_k.npy     vectores LSI de los documentos (documentos × k) = Σ_k⁻¹ U_kᵀ d
    lsi_sigma.npy      todos los valores singulares (curva de varianza explicada)
    manifiesto.json    fecha, modo de campos, N, |V|, IDF, k, criterio, hash de los datos de
                       entrada, hash del tokenizador y SHA-256 de cada archivo

``cargar`` comprueba el SHA-256 de cada archivo contra el manifiesto antes de usarlo.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy import sparse

from config import ENTREGA2_DIR
from lsi import ModeloLSI
from tfidf import ModeloTFIDF

INDICE_DIR = ENTREGA2_DIR / "indice"


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def hash_tokenizador() -> str:
    return _sha256(Path(__file__).with_name("tokenizer.py"))


def guardar(directorio: Path, ids: list[str], tf: ModeloTFIDF, lsi: ModeloLSI, *, modo: str, hash_entrada: str,
            fuente: str, extra: dict | None = None) -> dict:
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "vocabulario.json").write_text(json.dumps(tf.vocabulario, ensure_ascii=False))
    (directorio / "doc_ids.json").write_text(json.dumps(ids, ensure_ascii=False))
    np.save(directorio / "df.npy", tf.df)
    np.save(directorio / "idf.npy", tf.idf)
    sparse.save_npz(directorio / "tfidf.npz", tf.matriz)
    np.save(directorio / "lsi_U_k.npy", lsi.u_k)
    np.save(directorio / "lsi_sigma_k.npy", lsi.s_k)
    np.save(directorio / "lsi_docs_k.npy", lsi.docs_k)
    np.save(directorio / "lsi_sigma.npy", lsi.s_todos)
    archivos = sorted(p.name for p in directorio.iterdir() if p.name != "manifiesto.json")
    manifiesto = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": fuente,
        "modo_campos": modo,
        "N": len(ids),
        "tamano_vocabulario": len(tf.vocabulario),
        "idf": tf.variante,
        "tf": "conteo crudo",
        "normalizacion": "L2 por documento",
        "lsi": {"k": lsi.k, "umbral": lsi.umbral, "criterio": lsi.criterio,
                "descripcion_criterio": (f"menor k con sum_(2<=i<=k) s_i^2 / sum_(i>=2) s_i^2 >= {lsi.umbral:.0%} "
                                         "(sin la primera componente, que se conserva en el modelo)"
                                         if lsi.criterio == "sin_primera" else
                                         f"menor k con sum_(i<=k) s_i^2 / sum_i s_i^2 >= {lsi.umbral:.0%}"),
                "varianza_explicada_k": lsi.varianza_k, "varianza_sin_primera_k": lsi.varianza_sin_primera_k,
                "n_valores_singulares": int(lsi.s_todos.size),
                "transformacion": "x_k = Sigma_k^-1 U_k^T x (documentos y consultas)"},
        "hash_datos_entrada": hash_entrada,
        "hash_tokenizador": hash_tokenizador(),
        "versiones": {"numpy": np.__version__, "scipy": scipy.__version__},
        "archivos": {n: {"sha256": _sha256(directorio / n), "bytes": (directorio / n).stat().st_size} for n in archivos},
        **(extra or {}),
    }
    (directorio / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False))
    return manifiesto


@dataclass
class Indice:
    manifiesto: dict
    ids: list[str]
    tfidf: ModeloTFIDF
    lsi: ModeloLSI


def cargar(directorio: Path = INDICE_DIR, verificar: bool = True) -> Indice:
    man = json.loads((directorio / "manifiesto.json").read_text())
    if verificar:
        for nombre, info in man["archivos"].items():
            if _sha256(directorio / nombre) != info["sha256"]:
                raise ValueError(f"{nombre}: el SHA-256 no coincide con el manifiesto")
    ids = json.loads((directorio / "doc_ids.json").read_text())
    vocab = json.loads((directorio / "vocabulario.json").read_text())
    tf = ModeloTFIDF(vocab, np.load(directorio / "df.npy"), np.load(directorio / "idf.npy"),
                     sparse.load_npz(directorio / "tfidf.npz").tocsr(), man["N"], man["idf"])
    lsi = ModeloLSI(np.load(directorio / "lsi_U_k.npy"), np.load(directorio / "lsi_sigma_k.npy"),
                    np.load(directorio / "lsi_docs_k.npy"), np.load(directorio / "lsi_sigma.npy"),
                    man["lsi"]["k"], man["lsi"]["umbral"], man["lsi"]["criterio"])
    return Indice(man, ids, tf, lsi)


def actualizar_manifiesto(directorio: Path, seccion: str, meta: dict) -> dict:
    """Agrega o reemplaza ``manifiesto[seccion]`` y recalcula el SHA-256 de todos los archivos.

    Se usa para las estructuras de la Fase 4 (K-Means, LSH), que se guardan junto al índice.
    """
    ruta = directorio / "manifiesto.json"
    man = json.loads(ruta.read_text())
    man[seccion] = {**meta, "actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    archivos = sorted(p.name for p in directorio.iterdir() if p.name != "manifiesto.json")
    man["archivos"] = {n: {"sha256": _sha256(directorio / n), "bytes": (directorio / n).stat().st_size}
                       for n in archivos}
    ruta.write_text(json.dumps(man, indent=2, ensure_ascii=False))
    return man


def hash_base(directorio: Path = INDICE_DIR) -> dict:
    """SHA-256 de las matrices de las que derivan K-Means y LSH (para detectar índices viejos)."""
    return {n: _sha256(directorio / n) for n in ("tfidf.npz", "lsi_docs_k.npy")}
