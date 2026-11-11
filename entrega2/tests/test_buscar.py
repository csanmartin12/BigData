"""Tests de la CLI de búsqueda (Fase 5) sobre el índice y la colección reales.

Requieren MongoDB (``infra/docker-compose.yml``) y ``entrega2/indice/``; se omiten si faltan.
**No requieren HDFS**: ``test_no_depende_de_hdfs`` corre la CLI con HDFS inaccesible (puertos
bloqueados e importaciones de ``hdfs_webhdfs`` / ``pyspark`` / ``requests`` prohibidas).
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.integracion

ENTREGA2 = Path(__file__).resolve().parent.parent
CLI = ENTREGA2 / "src" / "buscar.py"
PUERTOS_HDFS = (9870, 9864, 9866, 9867, 8020)


def _mongo_arriba() -> bool:
    try:
        from pymongo import MongoClient
        MongoClient(serverSelectionTimeoutMS=1500).admin.command("ping")
        return (ENTREGA2 / "indice" / "manifiesto.json").exists()
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def col():
    if not _mongo_arriba():
        pytest.skip("MongoDB o el índice no están disponibles")
    from pymongo import MongoClient
    c = MongoClient()
    yield c.eso.xshooter
    c.close()


def correr(*args, env=None) -> tuple[int, dict | str]:
    r = subprocess.run([sys.executable, str(CLI), *args, "--json"], capture_output=True, text=True, timeout=120,
                       env=env)
    if r.returncode != 0:
        return r.returncode, r.stderr
    return 0, json.loads(r.stdout)


def _header(col, arcfile):
    return col.find_one({"_id": arcfile}, {"header": 1})["header"]


# ---------------------------------------------------------------------------
# Solo semántica
# ---------------------------------------------------------------------------
# Con los hiperparámetros elegidos con consultas cortas (Fase 4b), las 6 configuraciones
# devuelven resultados para consultas cortas. (Con los de la primera validación, TF-IDF + LSH
# b = 16, L = 4 no encontraba candidatos: METODOLOGIA.md, Fase 4b.)
CONFIGS_CON_RESULTADOS = [(m, o) for m in ("tfidf", "lsi") for o in ("ninguna", "kmeans", "lsh")]


@pytest.mark.parametrize("modelo,optim", CONFIGS_CON_RESULTADOS)
def test_solo_semantica(col, modelo, optim):
    code, r = correr("--texto", "filt b", "--modelo", modelo, "--optim", optim, "--top", "5")
    assert code == 0, r
    assert r["modo"] == "semantica" and r["fuera_de_vocabulario"] == ["filt"] and r["tokens"] == ["filt", "b"]
    assert 1 <= len(r["resultados"]) <= 5
    puntajes = [x["puntaje"] for x in r["resultados"]]
    assert puntajes == sorted(puntajes, reverse=True) and all(p is not None for p in puntajes)
    assert all(x["hdfs_path"].startswith("/eso/xshooter/2026/09/") for x in r["resultados"])
    if modelo == "tfidf" and optim == "ninguna":  # el token exacto "b" decide: todos con FILT1 NAME = B
        assert all(_header(col, x["arcfile"])["ESO INS FILT1 NAME"] == "B" for x in r["resultados"])


# ---------------------------------------------------------------------------
# Solo numérica (Prueba E)
# ---------------------------------------------------------------------------
def test_solo_numerica_prueba_e(col):
    code, r = correr("--ra-min", "84", "--ra-max", "85", "--dec-min", "-70", "--dec-max", "-69")
    assert code == 0, r
    assert r["modo"] == "numerica" and r["n_candidatos_filtro"] == 18 and len(r["resultados"]) == 18
    ids = [x["arcfile"] for x in r["resultados"]]
    assert ids == sorted(ids)  # ordenados por _id
    assert all(x["puntaje"] is None for x in r["resultados"])
    for x in r["resultados"]:
        h = _header(col, x["arcfile"])
        assert 84 <= h["RA"] <= 85 and -70 <= h["DEC"] <= -69
        assert x["hdfs_path"] == col.find_one({"_id": x["arcfile"]})["storage"]["hdfs_path"]


def test_solo_numerica_fecha_categoria_exptime(col):
    code, r = correr("--fecha-desde", "2026-09-06", "--fecha-hasta", "2026-09-06", "--categoria", "science",
                     "--exptime-min", "400")
    assert code == 0, r
    esperados = sorted(d["_id"] for d in col.find({"search.dpr.catg": "SCIENCE", "search.exptime": {"$gte": 400},
                                                   "header.DATE-OBS": {"$regex": "^2026-09-06"}}, {"_id": 1}))
    assert [x["arcfile"] for x in r["resultados"]] == esperados and esperados


# ---------------------------------------------------------------------------
# Combinada (texto + filtro de MongoDB)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("modelo,optim", CONFIGS_CON_RESULTADOS)
def test_combinada_consulta_a(col, modelo, optim):
    code, r = correr("--texto", "flat sky", "--fecha-desde", "2026-09-05", "--fecha-hasta", "2026-09-05",
                     "--modelo", modelo, "--optim", optim, "--top", "10")
    assert code == 0, r
    assert r["modo"] == "combinada" and r["n_candidatos_filtro"] == 433
    assert r["resultados"] and all("/2026/09/05/" in x["hdfs_path"] for x in r["resultados"])
    assert r["n_examinados"] <= 433
    for x in r["resultados"]:  # todos pasan el filtro
        assert _header(col, x["arcfile"])["DATE-OBS"].startswith("2026-09-05")


@pytest.mark.parametrize("optim,modelo", [("kmeans", "tfidf"), ("kmeans", "lsi")])
def test_interseccion_vacia_se_informa_y_no_se_rellena(col, optim, modelo):
    code, r = correr("--texto", "flat sky", "--categoria", "SCIENCE", "--optim", optim, "--modelo", modelo)
    assert code == 0, r
    assert r["resultados"] == [] and r["n_examinados"] == 0
    assert any("intersección vacía" in a and "no se rellena" in a for a in r["avisos"])


def test_interseccion_vacia_lsh_se_informa(col):
    """Mismo contrato con LSH: índice sin buckets que contengan candidatos -> aviso, sin relleno."""
    sys.path.insert(0, str(ENTREGA2 / "src"))
    import numpy as np

    import lsh_indice
    from buscador import Buscador
    b = Buscador()
    try:
        real = b.lsh["lsi"]
        b.lsh["lsi"] = lsh_indice.IndiceLSH("lsi", real.hiperplanos, real.firmas,
                                            [{} for _ in range(real.n_tablas)], real.media, real.radio_max)
        r = b.buscar("flat sky", "lsi", "lsh", 10, fecha_desde="2026-09-05", fecha_hasta="2026-09-05")
        assert r.resultados == [] and r.n_examinados == 0 and r.n_candidatos_filtro == 433
        assert any("intersección vacía" in a and "no se rellena" in a for a in r.avisos)
    finally:
        b.cerrar()


def test_consulta_sin_terminos_y_sin_argumentos(col):
    code, r = correr("--texto", "filt ins")
    assert code == 0 and r["resultados"] == [] and r["fuera_de_vocabulario"] == ["filt", "ins"]
    assert any("norma 0" in a for a in r["avisos"])
    code, err = correr()
    assert code == 2 and "indique --texto" in err


# ---------------------------------------------------------------------------
# Independencia de HDFS
# ---------------------------------------------------------------------------
def test_no_depende_de_hdfs(col, tmp_path):
    """La CLI funciona con HDFS inaccesible y sin poder importar el cliente de HDFS ni Spark."""
    (tmp_path / "sitecustomize.py").write_text(textwrap.dedent(f"""
        import socket, sys
        PROHIBIDOS = {{"hdfs_webhdfs", "pyspark", "requests"}}
        class _Bloqueo:
            def find_spec(self, nombre, ruta=None, objetivo=None):
                if nombre.split(".")[0] in PROHIBIDOS:
                    raise ImportError(f"importación prohibida en la búsqueda: {{nombre}}")
                return None
        sys.meta_path.insert(0, _Bloqueo())
        _connect = socket.socket.connect
        def _connect_sin_hdfs(self, addr):
            if isinstance(addr, tuple) and len(addr) >= 2 and addr[1] in {PUERTOS_HDFS!r}:
                raise ConnectionRefusedError(f"HDFS inaccesible (simulado): {{addr}}")
            return _connect(self, addr)
        socket.socket.connect = _connect_sin_hdfs
    """))
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "ENTREGA2_WEBHDFS_URL": "http://127.0.0.1:1/webhdfs/v1"}
    # el bloqueo funciona: importar el cliente de HDFS falla en este entorno
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import hdfs_webhdfs"],
                       cwd=ENTREGA2, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "importación prohibida" in r.stderr
    for args in (["--texto", "ins opti 1.6x11", "--modelo", "lsi", "--optim", "lsh"],
                 ["--ra-min", "84", "--ra-max", "85", "--dec-min", "-70", "--dec-max", "-69"],
                 ["--texto", "flat sky", "--fecha-desde", "2026-09-05", "--fecha-hasta", "2026-09-05",
                  "--optim", "kmeans"]):
        code, out = correr(*args, env=env)
        assert code == 0, out
        assert out["resultados"] and all(x["hdfs_path"].startswith("/eso/xshooter/") for x in out["resultados"])


# ---------------------------------------------------------------------------
# Fase 6: buscador del benchmark
# ---------------------------------------------------------------------------
def test_exhaustiva_sin_copia_es_identica_bit_a_bit(col):
    import numpy as np
    from buscador import Buscador
    b = Buscador(verificar=False)
    for e, esp in b.espacios.items():
        for txt in ("filt b", "exp type normal", "ins opti 1.6x11"):
            q_tf, _ = b.ix.tfidf.vectorizar_consulta(__import__("tokenizer").tokenizar(txt))
            q = __import__("espacios").vector_consulta(b.ix, e, q_tf)
            assert np.array_equal(esp.cosenos(q), esp.cosenos(q, np.arange(esp.x.shape[0])))
    assert all(p["num_threads"] == 1 for p in b.blas)  # BLAS a 1 hilo (config.HILOS_BLAS)
    b.cerrar()


@pytest.mark.parametrize("modelo, optim", [("tfidf", "ninguna"), ("lsi", "kmeans"), ("tfidf", "lsh")])
def test_buscador_solo_carga_su_configuracion_y_da_lo_mismo(col, modelo, optim):
    from buscador import Buscador
    from consultas import ARGUMENTOS_CLI
    completo, solo = Buscador(verificar=False), Buscador(verificar=False, solo=(modelo, optim))
    assert set(solo.espacios) == {modelo}
    assert set(solo.kmeans) == ({modelo} if optim == "kmeans" else set())
    assert set(solo.lsh) == ({modelo} if optim == "lsh" else set())
    assert solo.ix.tfidf.matriz is None and (solo.ix.lsi is None) == (modelo == "tfidf")
    for c, kw in ARGUMENTOS_CLI.items():
        a, b_ = completo.buscar(modelo=modelo, optim=optim, **kw), solo.buscar(modelo=modelo, optim=optim, **kw)
        assert a.resultados == b_.resultados, c
    otro = ("lsi" if modelo == "tfidf" else "tfidf", optim)
    with pytest.raises(ValueError, match="solo cargó"):
        solo.buscar("filt b", modelo=otro[0], optim=otro[1])
    completo.cerrar()
    solo.cerrar()
