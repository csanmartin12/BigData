"""Corpus para TF-IDF/LSI, construido desde MongoDB (``eso.xshooter``, campo ``header``).

El enunciado pide indexar "con los datos dentro de su sistema": el corpus se lee de MongoDB,
no de ``headers.csv``. Cada documento se identifica por su ``_id`` (ARCFILE) y los documentos
se ordenan por ``_id``, así que la fila *i* de las matrices corresponde siempre al mismo ARCFILE.

Modos de campos (enunciado 3.3: "los campos de texto del encabezado"):

- ``texto`` (por defecto): solo los pares llave-valor cuyo valor es de tipo ``str``.
- ``todos``: todos los pares (bool, int, float y str), como el prototipo de la Fase 0.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from config import MONGO_COLECCION, MONGO_DB, MONGO_URI
from tokenizer import tokenizar

MODOS = ("texto", "todos")
MODO_POR_DEFECTO = "texto"


def campos_del_modo(header: dict, modo: str) -> dict:
    if modo == "texto":
        return {k: v for k, v in header.items() if isinstance(v, str)}
    if modo == "todos":
        return header
    raise ValueError(f"modo desconocido: {modo!r} (opciones: {MODOS})")


def leer_headers_mongo(uri: str = MONGO_URI, db: str = MONGO_DB, coleccion: str = MONGO_COLECCION) -> list[tuple[str, dict]]:
    from pymongo import MongoClient
    with MongoClient(uri) as c:
        return [(d["_id"], d["header"]) for d in c[db][coleccion].find({}, {"header": 1}).sort("_id", 1)]


def hash_datos(docs: list[tuple[str, dict]]) -> str:
    """SHA-256 de los datos de entrada (``_id`` + header en el orden del corpus)."""
    h = hashlib.sha256()
    for _id, header in docs:
        h.update(_id.encode())
        h.update(b"\0")
        h.update(json.dumps(header, ensure_ascii=False, separators=(",", ":"), default=str).encode())
        h.update(b"\n")
    return h.hexdigest()


@dataclass
class Corpus:
    modo: str
    ids: list[str]
    tokens: list[list[str]]
    hash_entrada: str
    headers: list[dict] = field(repr=False)

    @property
    def n(self) -> int:
        return len(self.ids)


def construir_corpus(modo: str = MODO_POR_DEFECTO, docs: list[tuple[str, dict]] | None = None) -> Corpus:
    """``docs`` permite pasar los headers ya leídos (tests o varios modos con una sola lectura)."""
    if docs is None:
        docs = leer_headers_mongo()
    docs = sorted(docs, key=lambda d: d[0])
    tokens = []
    for _id, header in docs:
        t: list[str] = []
        for llave, valor in campos_del_modo(header, modo).items():
            t.extend(tokenizar(valor, llave=llave))
        tokens.append(t)
    return Corpus(modo=modo, ids=[d[0] for d in docs], tokens=tokens, hash_entrada=hash_datos(docs),
                  headers=[d[1] for d in docs])
