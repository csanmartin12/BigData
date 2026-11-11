"""Integración de R1/R6: el ETL real (Spark + MongoDB + HDFS) sobre ZIP sintéticos.

Usa la base ``e2_test`` y la raíz HDFS ``/e2_test`` (no toca ``eso`` ni ``/eso``). Se omite si
los servicios de ``infra/docker-compose.yml`` no están arriba.

Corrida 1 (``--limpiar``), ZIP T1 = {A bueno, T truncado, C con CRC dañado, N sin ARCFILE}:
    insertados 1 · revisión: ilegible 2, sin_arcfile 1.
Corrida 2 (sin limpiar), T1 + T2 = {A idéntico, A' mismo ARCFILE con otro contenido} + T3 ilegible:
    insertados 0 · omitidos idénticos 2 (A de T1 y de T2) · revisión: ilegible 2, sin_arcfile 1,
    conflicto_arcfile 1 · ZIP ilegibles 1. La ruta principal de A conserva el contenido original.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from sinteticos import danar_miembro, escribir_zip, fits_bytes, zip_ilegible

pytestmark = pytest.mark.integracion

ENTREGA2 = Path(__file__).resolve().parent.parent
DB, RAIZ = "e2_test", "/e2_test"
ENV = {"ENTREGA2_MONGO_DB": DB, "ENTREGA2_HDFS_RAIZ": f"{RAIZ}/xshooter",
       "ENTREGA2_HDFS_REVISION": f"{RAIZ}/revision"}
WEBHDFS = "http://localhost:9870/webhdfs/v1"
A = "XSHOO.2026-01-01T00:00:00.000.fits"
RUTA_A = f"{RAIZ}/xshooter/2026/01/01/XSHOO.2026-01-01T00_00_00.000.fits"


def _servicios_arriba() -> bool:
    try:
        from pymongo import MongoClient
        MongoClient(serverSelectionTimeoutMS=1500).admin.command("ping")
        return requests.get(f"{WEBHDFS}/?op=GETFILESTATUS&user.name=hadoop", timeout=2).ok
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def entorno():
    if not _servicios_arriba():
        pytest.skip("MongoDB/HDFS no disponibles (docker compose -f infra/docker-compose.yml up -d)")
    from pymongo import MongoClient
    cliente = MongoClient()
    yield cliente[DB]
    cliente.drop_database(DB)
    requests.delete(f"{WEBHDFS}{RAIZ}", params={"op": "DELETE", "recursive": "true", "user.name": "hadoop"})


def _etl(data_dir: Path, salidas: Path, *extra) -> dict:
    env = {**os.environ, **ENV, "ENTREGA2_SALIDAS_DIR": str(salidas)}
    r = subprocess.run([sys.executable, str(ENTREGA2 / "src" / "etl.py"), "--data-dir", str(data_dir),
                        "--hilos", "2", "--etiqueta", "test", *extra],
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    ultimo = sorted(salidas.glob("etl_*_test.json"))[-1]
    metricas = json.loads(ultimo.read_text())
    ultimo.unlink()  # la siguiente corrida busca su propio archivo
    return metricas


def _abrir(ruta: str) -> bytes:
    r = requests.get(f"{WEBHDFS}{ruta}", params={"op": "OPEN", "user.name": "hadoop"})
    r.raise_for_status()
    return r.content


def test_r1_r6_de_punta_a_punta(entorno, tmp_path):
    a = fits_bytes(A, contenido=b"A")
    a_prima = fits_bytes(A, contenido=b"Z")  # mismo ARCFILE, otro contenido
    d1, d2, sal = tmp_path / "d1", tmp_path / "d2", tmp_path / "salidas"
    for d in (d1, d2):
        d.mkdir()
    t1 = {A: a, "XSHOO.2026-01-01T00:00:01.000.fits": fits_bytes("XSHOO.T.fits", con_end=False),
          "XSHOO.2026-01-01T00:00:02.000.fits": fits_bytes("XSHOO.C.fits", contenido=b"Q"),
          "XSHOO.2026-01-01T00:00:03.000.fits": fits_bytes(None, contenido=b"N")}
    for d in (d1, d2):
        danar_miembro(escribir_zip(d / "XSHOO.T1.zip", t1), b"QQQQ")
    escribir_zip(d2 / "XSHOO.T2.zip", {A: a, "XSHOO.2026-01-01T00:00:00.000_otra.fits": a_prima})
    zip_ilegible(d2 / "XSHOO.T3.zip")

    # ---- corrida 1 ----
    m1 = _etl(d1, sal, "--limpiar")
    assert m1["carga"] == {"insertados": 1, "omitidos_identicos": 0,
                           "revision": {"ilegible": 2, "sin_arcfile": 1}, "revision_total": 3,
                           "zips_ilegibles": 0, "bytes_subidos": len(a)}
    assert m1["spark"]["trabajo_en_tareas_spark"] is True

    # ---- corrida 2: idempotencia, duplicado idéntico, conflicto y ZIP ilegible ----
    m2 = _etl(d2, sal)
    assert m2["carga"]["insertados"] == 0
    assert m2["carga"]["omitidos_identicos"] == 2
    assert m2["carga"]["revision"] == {"ilegible": 2, "sin_arcfile": 1, "conflicto_arcfile": 1}
    assert m2["carga"]["zips_ilegibles"] == 1

    col, rev = entorno["xshooter"], entorno["revision"]
    assert col.count_documents({}) == 1
    doc = col.find_one({"_id": A})
    assert doc["storage"]["sha256"] == hashlib.sha256(a).hexdigest()
    assert doc["storage"]["source"]["zip"] == "XSHOO.T1.zip"  # el primero registrado se conserva
    assert _abrir(RUTA_A) == a  # el conflicto no tocó la ruta principal

    por_motivo = {}
    for r in rev.find():
        por_motivo.setdefault(r["motivo"], []).append(r)
    assert {k: len(v) for k, v in por_motivo.items()} == {"ilegible": 3, "sin_arcfile": 1, "conflicto_arcfile": 1}
    (conf,) = por_motivo["conflicto_arcfile"]
    assert (conf["arcfile"], conf["zip"], conf["sha256"], conf["sha256_existente"]) == (
        A, "XSHOO.T2.zip", hashlib.sha256(a_prima).hexdigest(), hashlib.sha256(a).hexdigest())
    assert _abrir(conf["revision_hdfs_path"]) == a_prima  # separado para revisión, no eliminado
    ilegibles = {(r["zip"], r["miembro"], r["etapa"]) for r in por_motivo["ilegible"]}
    assert ilegibles == {("XSHOO.T1.zip", "XSHOO.2026-01-01T00:00:01.000.fits", "leer_header"),
                         ("XSHOO.T1.zip", "XSHOO.2026-01-01T00:00:02.000.fits", "leer_zip"),
                         ("XSHOO.T3.zip", None, "listar_zip")}
    assert all(r["error"] for r in por_motivo["ilegible"])
