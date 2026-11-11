"""Tests de la extracción de headers y del documento de MongoDB (Fase 1)."""
import io

import pytest

from documento import construir_documento, ruta_hdfs
from fits_header import (
    HeaderFITSInvalido, contar_sin_info, es_miembro_fits, leer_header, parsear_tarjeta,
)


def tarjeta(texto: str) -> str:
    return texto.ljust(80)


def fits_sintetico(tarjetas: list[str]) -> bytes:
    cuerpo = "".join(tarjeta(t) for t in tarjetas + ["END"])
    cuerpo = cuerpo.ljust(-(-len(cuerpo) // 2880) * 2880)
    return cuerpo.encode("ascii") + b"\0" * 2880


class TestTarjetas:
    @pytest.mark.parametrize("t, esperado", [
        ("SIMPLE  =                    T / Standard FITS", ("SIMPLE", True)),
        ("EXTEND  =                    F", ("EXTEND", False)),
        ("NAXIS1  =                  562 / # of pixels", ("NAXIS1", 562)),
        ("BZERO   =         3.276800E+04 / real", ("BZERO", 32768.0)),
        ("CRVAL1  =           1.5D-02", ("CRVAL1", 0.015)),
        ("ORIGIN  = 'ESO     '           / European Southern Observatory", ("ORIGIN", "ESO")),
        ("OBSERVER= 'O''Brien'", ("OBSERVER", "O'Brien")),
        ("OBJECT  = ''", ("OBJECT", "")),
        ("OBJECT  = '  lead'", ("OBJECT", "  lead")),
        ("TELESCOP= 'Tel name not set'   / ESO <TEL>", ("TELESCOP", "Tel name not set")),
        ("HIERARCH ESO DET CHIP1 ID    = 'CCD57-10IE' / Detector chip", ("ESO DET CHIP1 ID", "CCD57-10IE")),
        ("HIERARCH ESO DET CHIP FRMXFER=            T / chip", ("ESO DET CHIP FRMXFER", True)),
        ("HIERARCH ESO DPR TYPE = 'FLAT,SKY' / Observation type", ("ESO DPR TYPE", "FLAT,SKY")),
        ("HIERARCH ESO TEL AIRM START = 1.234 / comment with = sign", ("ESO TEL AIRM START", 1.234)),
    ])
    def test_valores_tipados_como_astropy(self, t, esperado):
        assert parsear_tarjeta(tarjeta(t)) == esperado

    @pytest.mark.parametrize("t", [
        "COMMENT   texto libre", "HISTORY   algo", "CONTINUE  'resto'", "", "        sin llave",
    ])
    def test_tarjetas_excluidas(self, t):
        assert parsear_tarjeta(tarjeta(t)) is None


def test_una_ocurrencia_por_llave_y_exclusiones():
    datos = fits_sintetico([
        "SIMPLE  =                    T", "OBJECT  = 'primero'", "COMMENT hola", "",
        "OBJECT  = 'segundo'", "HISTORY x", "HIERARCH ESO DPR CATG = 'CALIB'",
    ])
    assert leer_header(io.BytesIO(datos)) == {"SIMPLE": True, "OBJECT": "primero", "ESO DPR CATG": "CALIB"}


def test_no_fits_y_truncado():
    with pytest.raises(HeaderFITSInvalido):
        leer_header(io.BytesIO(b"\0" * 2880))
    with pytest.raises(HeaderFITSInvalido):
        leer_header(io.BytesIO(tarjeta("SIMPLE  =                    T").encode() * 36))  # sin END


@pytest.mark.parametrize("nombre, esperado", [
    ("XSHOO.2026-09-07T10:05:27.698.fits", True),
    ("__MACOSX/._XSHOO.2026-09-07T10:05:27.698.fits", False),
    ("carpeta/._XSHOO.fits", False),
    ("notas.txt", False),
])
def test_miembros_fits(nombre, esperado):
    assert es_miembro_fits(nombre) is esperado


def test_contar_sin_info():
    h = {"A": "", "B": "UNKNOWN", "C": "Tel name not set", "D": "LAMP,AFC", "E": 0, "F": False}
    assert contar_sin_info(h) == 3


def test_ruta_hdfs_sin_dos_puntos():
    assert ruta_hdfs("XSHOO.2026-09-04T01:43:37.983.fits", "2026-09-04T01:43:37.983") == \
        "/eso/xshooter/2026/09/04/XSHOO.2026-09-04T01_43_37.983.fits"


def _header(**extra):
    h = {"ARCFILE": "XSHOO.2026-09-05T22:54:01.123.fits", "DATE-OBS": "2026-09-05T22:54:01.123",
         "MJD-OBS": 61289.95, "EXPTIME": 5.0, "INSTRUME": "XSHOOTER", "TELESCOP": "ESO-VLT-U3",
         "OBJECT": "LAMP,AFC", "ESO DPR CATG": "CALIB", "ESO DPR TYPE": "LAMP,AFC", "ESO DPR TECH": "IMAGE",
         "ESO OBS PROG ID": "60.A-9022(C)", "CHECKSUM": "abc", "DATASUM": "123"}
    h.update(extra)
    return h


def test_documento_figura3_con_coordenadas():
    doc = construir_documento(_header(RA=84.5, DEC=-69.5), source_zip="z.zip", source_file="f.fits",
                              size_bytes=10, sha256="00")
    assert set(doc) == {"_id", "search", "storage", "header"}
    assert doc["_id"] == "XSHOO.2026-09-05T22:54:01.123.fits"
    s = doc["search"]
    assert s["ra"] == 84.5 and s["dec"] == -69.5 and s["tiene_coordenadas"] is True  # grados originales
    assert "geo" not in s and "coordenadas" not in s
    assert s["date_obs"].isoformat() == "2026-09-05T22:54:01.123000+00:00"
    assert s["dpr"] == {"catg": "CALIB", "type": "LAMP,AFC", "tech": "IMAGE"}
    assert (s["object"], s["program_id"], s["instrument"], s["telescope"]) == (
        "LAMP,AFC", "60.A-9022(C)", "XSHOOTER", "ESO-VLT-U3")
    assert (s["mjd_obs"], s["exptime"], s["indexado"]) == (61289.95, 5.0, True)
    st = doc["storage"]
    assert st["hdfs_path"] == "/eso/xshooter/2026/09/05/XSHOO.2026-09-05T22_54_01.123.fits"
    assert (st["checksum"], st["datasum"], st["size_bytes"], st["sha256"]) == ("abc", "123", 10, "00")
    assert st["source"] == {"zip": "z.zip", "file": "f.fits"}
    assert doc["header"]["ARCFILE"] == "XSHOO.2026-09-05T22:54:01.123.fits"  # header completo, original
    assert doc["header"]["RA"] == 84.5


def test_documento_sin_coordenadas_no_imputa():
    doc = construir_documento(_header(), source_zip="z", source_file="f", size_bytes=1)
    s = doc["search"]
    assert "ra" not in s and "dec" not in s  # ni null ni valores inventados
    assert s["tiene_coordenadas"] is False


def test_documento_coordenadas_se_evaluan_como_par():
    s = construir_documento(_header(RA=84.5), source_zip="z", source_file="f", size_bytes=1)["search"]
    assert s["ra"] == 84.5 and "dec" not in s and s["tiene_coordenadas"] is False


def test_filtro_caja_prueba_e():
    from consultas import PRUEBA_E, filtro_caja_coordenadas
    assert filtro_caja_coordenadas(**PRUEBA_E) == {
        "search.ra": {"$gte": 84.0, "$lte": 85.0}, "search.dec": {"$gte": -70.0, "$lte": -69.0}}
