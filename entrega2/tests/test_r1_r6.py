"""Tests unitarios de R1/R6 (Informe 1, Tabla 11) con dobles en memoria de MongoDB y HDFS."""
import copy
import hashlib

import pytest
from pymongo.errors import DuplicateKeyError

from carga import (
    CONFLICTO_ARCFILE, ERROR_HDFS, ILEGIBLE, INSERTADO, OMITIDO_IDENTICO, SIN_ARCFILE, cargar_documento,
    registrar_revision,
)
from documento import construir_documento
from etl import extraer, planificar, transformar
from fits_header import leer_header_bytes
from sinteticos import danar_miembro, escribir_zip, fits_bytes, zip_ilegible

ARC = "XSHOO.2026-01-01T00:00:00.000.fits"


class ColeccionFalsa:
    """Lo mínimo de pymongo.Collection que usa carga.py, con _id único."""

    def __init__(self):
        self.docs = {}

    def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key error")
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    def find_one(self, filtro, proyeccion=None):
        return copy.deepcopy(self.docs.get(filtro["_id"]))

    def delete_one(self, filtro):
        d = self.docs.get(filtro["_id"])
        if d is not None and d["storage"]["sha256"] == filtro.get("storage.sha256", d["storage"]["sha256"]):
            del self.docs[filtro["_id"]]

    def replace_one(self, filtro, doc, upsert=False):
        assert upsert or filtro["_id"] in self.docs
        self.docs[filtro["_id"]] = copy.deepcopy(doc)


class HDFSFalso:
    def __init__(self, falla_en=()):
        self.archivos, self.escrituras, self.falla_en = {}, [], set(falla_en)

    def crear(self, ruta, datos, sobrescribir=True):
        if ruta in self.falla_en:
            raise RuntimeError("WebHDFS CREATE: HTTP 500")
        self.escrituras.append(ruta)
        self.archivos[ruta] = bytes(datos)


def _doc(datos: bytes, zip_name="z1.zip", miembro=ARC):
    h = leer_header_bytes(datos)
    return construir_documento(h, source_zip=zip_name, source_file=miembro, size_bytes=len(datos),
                               sha256=hashlib.sha256(datos).hexdigest())


RUTA = "/eso/xshooter/2026/01/01/XSHOO.2026-01-01T00_00_00.000.fits"


# ---------------------------------------------------------------------------
# R1
# ---------------------------------------------------------------------------
def test_r1_archivo_nuevo_se_inserta_y_sube():
    col, hdfs = ColeccionFalsa(), HDFSFalso()
    datos = fits_bytes(ARC)
    assert cargar_documento(_doc(datos), datos, col, hdfs) == (INSERTADO, {})
    assert set(col.docs) == {ARC} and hdfs.archivos[RUTA] == datos


def test_r1_duplicado_identico_se_omite_sin_volver_a_subir():
    col, hdfs = ColeccionFalsa(), HDFSFalso()
    datos = fits_bytes(ARC)
    cargar_documento(_doc(datos), datos, col, hdfs)
    resultado = cargar_documento(_doc(datos, zip_name="z2.zip"), datos, col, hdfs)
    assert resultado == (OMITIDO_IDENTICO, {})
    assert hdfs.escrituras == [RUTA]  # una sola subida
    assert col.docs[ARC]["storage"]["source"]["zip"] == "z1.zip"  # el registrado no cambia


def test_r1_duplicado_con_otro_contenido_va_a_revision_sin_tocar_la_ruta_principal():
    col, rev, hdfs = ColeccionFalsa(), ColeccionFalsa(), HDFSFalso()
    original, distinto = fits_bytes(ARC, contenido=b"A"), fits_bytes(ARC, contenido=b"B")
    sha_o, sha_d = hashlib.sha256(original).hexdigest(), hashlib.sha256(distinto).hexdigest()
    assert sha_o != sha_d
    cargar_documento(_doc(original), original, col, hdfs)
    resultado, detalle = cargar_documento(_doc(distinto, zip_name="z2.zip"), distinto, col, hdfs)
    assert resultado == CONFLICTO_ARCFILE and detalle == {"sha256_existente": sha_o}
    assert col.docs[ARC]["storage"]["sha256"] == sha_o  # no se sobrescribió
    assert hdfs.archivos[RUTA] == original and hdfs.escrituras == [RUTA]  # ruta principal intacta

    r = registrar_revision(rev, hdfs, motivo=resultado, etapa="cargar", zip_name="z2.zip", miembro=ARC,
                           arcfile=ARC, sha256=sha_d, datos=distinto, sha256_existente=sha_o)
    assert set(rev.docs) == {r["_id"]}
    assert (r["motivo"], r["arcfile"], r["sha256"], r["sha256_existente"]) == (CONFLICTO_ARCFILE, ARC, sha_d, sha_o)
    assert r["revision_hdfs_path"] == f"/eso/revision/{sha_d}.fits"  # copia fuera de la ruta principal
    assert hdfs.archivos[r["revision_hdfs_path"]] == distinto and hdfs.archivos[RUTA] == original


def test_r1_error_de_hdfs_libera_el_reclamo():
    col, hdfs = ColeccionFalsa(), HDFSFalso(falla_en={RUTA})
    datos = fits_bytes(ARC)
    resultado, detalle = cargar_documento(_doc(datos), datos, col, hdfs)
    assert resultado == ERROR_HDFS and "HTTP 500" in detalle["error"]
    assert col.docs == {}  # el ARCFILE queda libre para un reintento


def test_revision_idempotente():
    rev = ColeccionFalsa()
    for _ in range(2):
        registrar_revision(rev, None, motivo=ILEGIBLE, etapa="leer_header", zip_name="z.zip", miembro="m.fits",
                           error="HeaderFITSInvalido: x", sha256="ab")
    assert len(rev.docs) == 1


# ---------------------------------------------------------------------------
# R6 (etapas extraer / transformar del ETL y plan del driver)
# ---------------------------------------------------------------------------
def _tarea(ruta_zip, miembro, tamano=0):
    return {"zip": str(ruta_zip), "zip_name": ruta_zip.name, "miembro": miembro, "tamano": tamano, "comprimido": 0}


def test_r6_fits_truncado_va_a_revision_y_el_resto_sigue(tmp_path):
    z = escribir_zip(tmp_path / "XSHOO.T.zip", {
        "a_truncado.fits": fits_bytes("XSHOO.A.fits", con_end=False),
        "b_bueno.fits": fits_bytes("XSHOO.B.fits"),
    })
    regs = list(extraer([[_tarea(z, "a_truncado.fits"), _tarea(z, "b_bueno.fits")]]))
    assert [r["tipo"] for r in regs] == ["revision", "ok"]
    r = regs[0]
    assert (r["motivo"], r["etapa"], r["tarea"]["zip_name"], r["tarea"]["miembro"]) == (
        ILEGIBLE, "leer_header", "XSHOO.T.zip", "a_truncado.fits")
    assert "END" in r["error"] and r["datos"] is not None and r["sha256"]
    assert regs[1]["header"]["ARCFILE"] == "XSHOO.B.fits"


def test_r6_miembro_danado_en_el_zip(tmp_path):
    z = escribir_zip(tmp_path / "XSHOO.C.zip", {"c.fits": fits_bytes("XSHOO.C.fits", contenido=b"Q")})
    danar_miembro(z, b"QQQQ")
    (r,) = list(extraer([[_tarea(z, "c.fits")]]))
    assert (r["tipo"], r["motivo"], r["etapa"]) == ("revision", ILEGIBLE, "leer_zip")
    assert "BadZipFile" in r["error"] and r["datos"] is None


def test_r6_header_sin_arcfile_y_fecha_invalida(tmp_path):
    z = escribir_zip(tmp_path / "XSHOO.N.zip", {
        "n.fits": fits_bytes(None), "f.fits": fits_bytes("XSHOO.F.fits", date_obs="ayer"),
    })
    regs = list(transformar(extraer([[_tarea(z, "n.fits"), _tarea(z, "f.fits")]])))
    assert [(r["tipo"], r["motivo"]) for r in regs] == [("revision", SIN_ARCFILE), ("revision", "header_invalido")]
    assert "DATE-OBS" in regs[1]["error"]


def test_r6_zip_ilegible_no_detiene_el_plan(tmp_path):
    bueno = escribir_zip(tmp_path / "XSHOO.1.zip", {"x.fits": fits_bytes("XSHOO.X.fits")})
    malo = zip_ilegible(tmp_path / "XSHOO.2.zip")
    tareas, ilegibles = planificar([bueno, malo])
    assert [t["miembro"] for t in tareas] == ["x.fits"]  # __MACOSX/._x.fits se ignora
    assert len(ilegibles) == 1 and ilegibles[0]["zip_name"] == "XSHOO.2.zip"
    assert "BadZipFile" in ilegibles[0]["error"]
