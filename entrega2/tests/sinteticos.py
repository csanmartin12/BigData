"""FITS y ZIP sintéticos para los tests de R1/R6 (no dependen de los datos reales)."""
from __future__ import annotations

import zipfile
from pathlib import Path

BLOQUE = 2880


def _tarjeta(llave: str, valor) -> str:
    if isinstance(valor, str):
        v = "'" + valor.replace("'", "''") + "'"
    elif isinstance(valor, bool):
        v = "T" if valor else "F"
    else:
        v = str(valor)
    if llave.startswith("HIERARCH ") or len(llave) > 8:
        t = f"{llave if llave.startswith('HIERARCH ') else 'HIERARCH ' + llave} = {v}"
    else:
        t = f"{llave:<8}= {v:>20}" if not isinstance(valor, str) else f"{llave:<8}= {v}"
    assert len(t) <= 80, t
    return t.ljust(80)


def fits_bytes(arcfile: str | None, date_obs: str = "2026-01-01T00:00:00.000", *, contenido: bytes = b"A",
               con_end: bool = True, extra: dict | None = None) -> bytes:
    """Header primario mínimo + un bloque de datos cuyo contenido decide el SHA-256."""
    h = {"SIMPLE": True, "BITPIX": 8, "NAXIS": 0, "DATE-OBS": date_obs, "MJD-OBS": 61041.0,
         "OBJECT": "BIAS", "INSTRUME": "XSHOOTER", "TELESCOP": "ESO-VLT-U3",
         "ESO DPR CATG": "CALIB", "ESO DPR TYPE": "BIAS", "ESO DPR TECH": "IMAGE"}
    if arcfile is not None:
        h["ARCFILE"] = arcfile
    h.update(extra or {})
    texto = "".join(_tarjeta(k, v) for k, v in h.items())
    if con_end:
        texto += "END".ljust(80)
        texto = texto.ljust(-(-len(texto) // BLOQUE) * BLOQUE)
        datos = (contenido * BLOQUE)[:BLOQUE]
        return texto.encode("ascii") + datos
    # truncado: un bloque completo de tarjetas sin END y luego se corta el archivo
    return texto.ljust(BLOQUE).encode("ascii")


def escribir_zip(ruta: Path, miembros: dict[str, bytes], con_macosx: bool = True) -> Path:
    with zipfile.ZipFile(ruta, "w", compression=zipfile.ZIP_STORED) as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos)
            if con_macosx:
                zf.writestr(f"__MACOSX/._{nombre}", b"\0\5\26\7metadatos de macOS")
    return ruta


def danar_miembro(ruta_zip: Path, marcador: bytes) -> None:
    """Cambia un byte de los datos almacenados (ZIP_STORED) tras ``marcador``: el CRC-32 deja
    de coincidir y ``ZipFile.read`` lanza ``BadZipFile``."""
    b = bytearray(ruta_zip.read_bytes())
    i = b.index(marcador) + len(marcador)
    b[i] ^= 0xFF
    ruta_zip.write_bytes(bytes(b))


def zip_ilegible(ruta: Path) -> Path:
    ruta.write_bytes(b"esto no es un ZIP" * 100)
    return ruta
