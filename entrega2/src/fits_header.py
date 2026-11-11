"""Lectura del header primario de archivos FITS sin astropy.

Se leen solo los bloques de 2.880 bytes hasta la tarjeta ``END`` (el header va al inicio del
archivo), así que un header se obtiene sin descomprimir la imagen completa del ZIP.

Reglas de extracción (METODOLOGIA.md, "Decisiones de extracción"):

- Se excluyen las tarjetas ``COMMENT``, ``HISTORY`` y ``CONTINUE``, las tarjetas en blanco y
  las que no tienen indicador de valor.
- Una ocurrencia por llave: si una llave se repite se conserva la primera (como
  ``dict(astropy.io.fits.Header)``).
- Las llaves ``HIERARCH`` se normalizan como en astropy: el texto entre ``HIERARCH `` y el
  primer ``=``, sin espacios en los extremos (``HIERARCH ESO DET CHIP FRMXFER=`` →
  ``ESO DET CHIP FRMXFER``).
- Los valores se tipan como en astropy: ``T``/``F`` → bool, enteros → int, reales → float
  (``D`` como exponente se acepta), cadenas → str con ``''`` → ``'`` y sin espacios finales.
  Un valor ausente se representa con ``None``.
"""
from __future__ import annotations

import re
import zipfile
from typing import BinaryIO, Iterator

BLOQUE = 2880
TARJETA = 80
EXCLUIDAS = frozenset({"COMMENT", "HISTORY", "CONTINUE"})

_RE_CADENA = re.compile(r"'((?:[^']|'')*)'")
_RE_ENTERO = re.compile(r"[+-]?\d+")
_RE_REAL = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([EeDd][+-]?\d+)?")


class HeaderFITSInvalido(ValueError):
    pass


def leer_tarjetas(fh: BinaryIO, max_bloques: int = 1000) -> tuple[list[str], int]:
    """Lee bloques desde ``fh`` hasta la tarjeta END.

    Devuelve ``(tarjetas, bytes_leidos)``; las tarjetas no incluyen END.
    """
    tarjetas: list[str] = []
    leidos = 0
    for _ in range(max_bloques):
        bloque = fh.read(BLOQUE)
        if len(bloque) < BLOQUE:
            raise HeaderFITSInvalido("archivo truncado antes de la tarjeta END")
        if leidos == 0 and not bloque.startswith(b"SIMPLE  ="):
            raise HeaderFITSInvalido("no es un FITS: falta SIMPLE en la primera tarjeta")
        leidos += BLOQUE
        for i in range(0, BLOQUE, TARJETA):
            tarjeta = bloque[i:i + TARJETA].decode("ascii")
            if tarjeta[:8].rstrip() == "END" and not tarjeta[8:].strip():
                return tarjetas, leidos
            tarjetas.append(tarjeta)
    raise HeaderFITSInvalido(f"no se encontró END en {max_bloques} bloques")


def _parsear_valor(texto: str):
    """Valor de una tarjeta (lo que sigue al indicador ``=``), con el comentario incluido."""
    t = texto.lstrip()
    if t.startswith("'"):
        m = _RE_CADENA.match(t)
        if m is None:
            raise HeaderFITSInvalido(f"cadena sin cerrar: {texto!r}")
        return m.group(1).replace("''", "'").rstrip()
    t = t.split("/", 1)[0].strip()
    if t == "":
        return None
    if t == "T":
        return True
    if t == "F":
        return False
    if _RE_ENTERO.fullmatch(t):
        return int(t)
    if _RE_REAL.fullmatch(t):
        return float(t.replace("D", "E").replace("d", "e"))
    raise HeaderFITSInvalido(f"valor no reconocido: {texto!r}")


def parsear_tarjeta(tarjeta: str) -> tuple[str, object] | None:
    """``(llave, valor)`` de una tarjeta, o ``None`` si la tarjeta se excluye."""
    clave8 = tarjeta[:8].rstrip()
    if clave8 in EXCLUIDAS or not tarjeta.strip():
        return None
    if clave8 == "HIERARCH" and tarjeta[8] == " " and "=" in tarjeta:
        llave, resto = tarjeta[9:].split("=", 1)
        return llave.strip(), _parsear_valor(resto)
    if tarjeta[8:10] == "= ":
        return clave8.upper(), _parsear_valor(tarjeta[10:])
    return None  # tarjeta sin valor (comentario sin llave estándar)


def header_desde_tarjetas(tarjetas: list[str]) -> dict:
    header: dict = {}
    for tarjeta in tarjetas:
        par = parsear_tarjeta(tarjeta)
        if par is not None and par[0] not in header:
            header[par[0]] = par[1]
    return header


def leer_header(fh: BinaryIO) -> dict:
    return header_desde_tarjetas(leer_tarjetas(fh)[0])


def leer_header_bytes(datos: bytes) -> dict:
    import io
    return leer_header(io.BytesIO(datos))


# ---------------------------------------------------------------------------
# ZIP de la Entrega 1
# ---------------------------------------------------------------------------
def es_miembro_fits(nombre: str) -> bool:
    """FITS reales del ZIP: se ignoran ``__MACOSX/`` y los ``._*`` de macOS."""
    base = nombre.rsplit("/", 1)[-1]
    return (
        nombre.lower().endswith(".fits")
        and not nombre.startswith("__MACOSX/")
        and not base.startswith("._")
    )


def miembros_fits(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Miembros FITS en orden alfabético de nombre."""
    return sorted((i for i in zf.infolist() if es_miembro_fits(i.filename)), key=lambda i: i.filename)


def iterar_headers_zip(zip_path) -> Iterator[tuple[str, dict]]:
    """``(nombre_miembro, header)`` de cada FITS del ZIP, leyendo solo el header."""
    with zipfile.ZipFile(zip_path) as zf:
        for info in miembros_fits(zf):
            with zf.open(info) as fh:
                yield info.filename, leer_header(fh)


# ---------------------------------------------------------------------------
# Columnas de control de headers.csv
# ---------------------------------------------------------------------------
_RE_SIN_INFO = re.compile(r"unknown|not set", re.IGNORECASE)


def es_sin_info(valor) -> bool:
    """Valor vacío (``''``) o que contiene "unknown"/"not set" (sin distinguir mayúsculas)."""
    return isinstance(valor, str) and (valor == "" or _RE_SIN_INFO.search(valor) is not None)


def contar_sin_info(header: dict) -> int:
    return sum(es_sin_info(v) for v in header.values())
