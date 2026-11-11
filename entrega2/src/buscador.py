"""Motor de búsqueda híbrido (Fase 5): MongoDB para los filtros + índice vectorial en archivos.

**No depende de HDFS ni de Spark**: no importa ``hdfs_webhdfs`` ni ``pyspark`` y no abre
conexiones a HDFS. Devuelve ``storage.hdfs_path`` tal como está guardado en MongoDB; el FITS se
recupera aparte si hace falta.

Flujo:
1. Si hay filtros numéricos o de categoría, MongoDB devuelve los ``_id`` candidatos usando sus
   índices (``date_obs``, ``ra_dec``, ``dpr_catg_type``; ``exptime`` no tiene índice en la
   Tabla 9 y se resuelve recorriendo la colección).
2. Si hay texto: se tokeniza y vectoriza con el mismo vocabulario e IDF y se calcula el coseno
   exacto solo sobre los candidatos:
   - ``ninguna``: todos los candidatos (o todo el corpus);
   - ``kmeans``: documentos del clúster sondeado ∩ candidatos del filtro;
   - ``lsh``: buckets (con multi-probe si hay menos de ``top``) ∩ candidatos del filtro.
   Si la intersección queda vacía **se informa** y no se rellena con otros documentos.
3. Salida: ``storage.hdfs_path`` con su puntaje, más los tokens fuera del vocabulario.
   Solo numérica: todos los que pasan el filtro, ordenados por ``_id``, sin puntaje.

BLAS corre con ``config.HILOS_BLAS`` hilos (1 por defecto; METODOLOGIA.md, Fase 6). Con
``solo=(modelo, optim)`` se cargan únicamente los índices de esa configuración (pasada de RAM
del benchmark).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

import indice as indice_mod
import kmeans_indice
import lsh_indice
from config import HILOS_BLAS, MONGO_COLECCION, MONGO_DB, MONGO_URI
from espacios import ESPACIOS, espacios_desde_indice, vector_consulta
from tokenizer import tokenizar
from validacion import ordenar_top

MODELOS = ("tfidf", "lsi")
OPTIMIZACIONES = ("ninguna", "kmeans", "lsh")


@dataclass
class Resultado:
    modo: str                                # semantica | numerica | combinada
    resultados: list[dict] = field(default_factory=list)  # arcfile, hdfs_path, puntaje
    tokens: list[str] = field(default_factory=list)
    fuera_de_vocabulario: list[str] = field(default_factory=list)
    filtro_mongo: dict | None = None
    n_candidatos_filtro: int | None = None
    n_examinados: int | None = None          # documentos con coseno exacto calculado
    avisos: list[str] = field(default_factory=list)
    detalle: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        d = asdict(self)
        if d["filtro_mongo"] is not None:
            d["filtro_mongo"] = _serializable(d["filtro_mongo"])
        return d


def _serializable(x):
    if isinstance(x, dict):
        return {k: _serializable(v) for k, v in x.items()}
    if isinstance(x, datetime):
        return x.isoformat()
    return x


def _fecha(texto: str, fin: bool) -> tuple[str, datetime]:
    """``AAAA-MM-DD`` (día completo) o ISO con hora. Devuelve (operador, instante UTC)."""
    t = datetime.fromisoformat(texto)
    t = t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)
    if fin and len(texto) == 10:  # solo fecha: hasta el final de ese día
        return "$lt", t + timedelta(days=1)
    return ("$lte" if fin else "$gte"), t


def filtro_mongo(fecha_desde=None, fecha_hasta=None, ra_min=None, ra_max=None, dec_min=None, dec_max=None,
                 exptime_min=None, exptime_max=None, categoria=None) -> dict:
    f: dict = {}

    def rango(campo, lo, hi):
        r = {}
        if lo is not None:
            r["$gte"] = float(lo)
        if hi is not None:
            r["$lte"] = float(hi)
        if r:
            f[campo] = r

    fecha = {}
    if fecha_desde:
        op, t = _fecha(fecha_desde, fin=False)
        fecha[op] = t
    if fecha_hasta:
        op, t = _fecha(fecha_hasta, fin=True)
        fecha[op] = t
    if fecha:
        f["search.date_obs"] = fecha
    rango("search.ra", ra_min, ra_max)
    rango("search.dec", dec_min, dec_max)
    rango("search.exptime", exptime_min, exptime_max)
    if categoria:
        f["search.dpr.catg"] = categoria.strip().upper()
    return f


def fijar_hilos_blas(n: int = HILOS_BLAS) -> list[dict]:
    """Limita los hilos de BLAS de este proceso (global y persistente). Devuelve el estado."""
    try:
        from threadpoolctl import threadpool_info, threadpool_limits
    except ImportError:  # sin threadpoolctl: queda lo que diga OPENBLAS_NUM_THREADS
        return []
    threadpool_limits(limits=n, user_api="blas")
    return [{k: p.get(k) for k in ("internal_api", "num_threads", "version")} for p in threadpool_info()
            if p.get("user_api") == "blas"]


class Buscador:
    def __init__(self, directorio=indice_mod.INDICE_DIR, mongo_uri: str = MONGO_URI, verificar: bool = True,
                 solo: tuple[str, str] | None = None, hilos_blas: int | None = HILOS_BLAS):
        from pymongo import MongoClient
        if solo is not None and (solo[0] not in MODELOS or solo[1] not in OPTIMIZACIONES):
            raise ValueError(f"solo = (modelo en {MODELOS}, optim en {OPTIMIZACIONES})")
        self.solo = solo
        self.blas = fijar_hilos_blas(hilos_blas) if hilos_blas else []
        self.ix = indice_mod.cargar(directorio, verificar=verificar)
        modelos = ESPACIOS if solo is None else (solo[0],)
        self.espacios = espacios_desde_indice(self.ix, modelos)
        self.kmeans = {e: kmeans_indice.cargar(directorio, e) for e in modelos
                       if solo is None or solo[1] == "kmeans"}
        self.lsh = {e: lsh_indice.cargar(directorio, e) for e in modelos if solo is None or solo[1] == "lsh"}
        if solo is not None:  # liberar lo que esta configuración no usa al consultar
            self.ix.tfidf.matriz = None        # ya copiada como espacio denso (o no se usa)
            self.ix.lsi.docs_k = None          # ídem
            self.ix.lsi.s_todos = None
            if solo[0] == "tfidf":
                self.ix.lsi = None             # la proyección solo hace falta en LSI
        self.ids = self.ix.ids
        self.pos = {d: i for i, d in enumerate(self.ids)}
        self.cliente = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self.col = self.cliente[MONGO_DB][MONGO_COLECCION]

    def cerrar(self) -> None:
        self.cliente.close()

    def _rutas(self, ids: list[str]) -> dict[str, str]:
        return {d["_id"]: d["storage"]["hdfs_path"]
                for d in self.col.find({"_id": {"$in": ids}}, {"storage.hdfs_path": 1})}

    def buscar(self, texto: str | None = None, modelo: str = "tfidf", optim: str = "ninguna", top: int = 10,
               n_probe: int = kmeans_indice.N_PROBE_POR_DEFECTO, **filtros) -> Resultado:
        if modelo not in MODELOS or optim not in OPTIMIZACIONES:
            raise ValueError(f"modelo en {MODELOS}, optim en {OPTIMIZACIONES}")
        if self.solo is not None and (modelo, optim) != self.solo:
            raise ValueError(f"este buscador solo cargó {self.solo}")
        f = filtro_mongo(**filtros)
        hay_texto = bool(texto and texto.strip())
        if not hay_texto and not f:
            raise ValueError("indique --texto, algún filtro, o ambos")
        r = Resultado(modo="combinada" if hay_texto and f else ("semantica" if hay_texto else "numerica"),
                      filtro_mongo=f or None)

        permitidos = None
        if f:
            ids_filtro = [d["_id"] for d in self.col.find(f, {"_id": 1})]
            fuera = [d for d in ids_filtro if d not in self.pos]
            if fuera:
                r.avisos.append(f"{len(fuera)} documentos del filtro no están en el índice vectorial "
                                "(índice desactualizado); se ignoran")
            idx = np.array(sorted(self.pos[d] for d in ids_filtro if d in self.pos), dtype=np.int64)
            r.n_candidatos_filtro = int(idx.size)
            permitidos = np.zeros(len(self.ids), dtype=bool)
            permitidos[idx] = True

        if not hay_texto:  # solo numérica: todos, ordenados por _id, sin puntaje
            ids = sorted(self.ids[i] for i in np.flatnonzero(permitidos))
            rutas = self._rutas(ids)
            r.resultados = [{"arcfile": d, "hdfs_path": rutas.get(d), "puntaje": None} for d in ids]
            if not ids:
                r.avisos.append("ningún documento cumple el filtro")
            return r

        r.tokens = tokenizar(texto)
        q_tfidf, r.fuera_de_vocabulario = self.ix.tfidf.vectorizar_consulta(r.tokens)
        q = vector_consulta(self.ix, modelo, q_tfidf)
        if q is None:
            r.avisos.append("la consulta no tiene términos del vocabulario (vector de norma 0): sin resultados")
            return r
        if permitidos is not None and not permitidos.any():
            r.avisos.append("ningún documento cumple el filtro: sin resultados")
            return r

        if optim == "ninguna":
            cand = np.arange(len(self.ids)) if permitidos is None else np.flatnonzero(permitidos)
        elif optim == "kmeans":
            km = self.kmeans[modelo]
            docs, cl = km.candidatos(q, n_probe)
            cand = docs if permitidos is None else docs[permitidos[docs]]
            r.detalle = {"clusteres_sondeados": cl.tolist(), "docs_en_clusteres": int(docs.size)}
            if cand.size == 0:
                r.avisos.append(f"intersección vacía: el/los clúster(es) {cl.tolist()} ({docs.size} documentos) no "
                                f"contienen ninguno de los {r.n_candidatos_filtro} candidatos del filtro; "
                                "no se rellena con otros documentos")
        else:
            cand, info = self.lsh[modelo].candidatos(q, top, permitidos=permitidos)
            r.detalle = info
            if cand.size == 0:
                r.avisos.append("intersección vacía: los buckets (incluido multi-probe a Hamming 2) no contienen "
                                f"ninguno de los {r.n_candidatos_filtro if f else 'documentos'} candidatos; "
                                "no se rellena con otros documentos")
            elif cand.size < top:
                r.avisos.append(f"LSH encontró solo {cand.size} candidatos (< top = {top}) tras multi-probe")
        r.n_examinados = int(cand.size)
        if cand.size == 0:
            return r
        # Exhaustiva sobre todo el corpus: x @ q directo (sin copiar la matriz; mismo resultado
        # bit a bit que x[arange(N)] @ q). Con subconjunto: solo las filas candidatas.
        todo = optim == "ninguna" and permitidos is None
        t, s = ordenar_top(cand, self.espacios[modelo].cosenos(q, None if todo else cand), top)
        ids = [self.ids[i] for i in t]
        rutas = self._rutas(ids)
        r.resultados = [{"arcfile": d, "hdfs_path": rutas.get(d), "puntaje": float(p)} for d, p in zip(ids, s)]
        return r
