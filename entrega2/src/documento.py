"""Transformación de un header FITS al documento de MongoDB (search / storage / header).

Sigue la Figura 3 (estructura del documento), la Tabla 7 (campos principales) y la Tabla 9
(índices) del Informe 1 (``/mnt/c/Bases/main.typ``). Un documento por FITS, ``_id = ARCFILE``:

- ``search``: atributos para consultar o clasificar: ``object``, ``ra``, ``dec``,
  ``tiene_coordenadas``, ``date_obs`` (fecha), ``mjd_obs``, ``exptime``,
  ``dpr.{catg,type,tech}``, ``program_id``, ``instrument``, ``telescope``, e ``indexado``
  (Entrega 2: todas las categorías participan en el buscador).
- ``storage``: ``hdfs_path``, ``checksum`` y ``datasum`` (Informe 1); la Entrega 2 agrega
  ``size_bytes``, ``sha256``, ``source.{zip,file}`` y ``loaded_at`` para verificar la carga.
- ``header``: el header primario **completo** (llaves FITS originales, valores tipados, una
  ocurrencia por llave). Desviación respecto del Informe 1, donde ``header`` guarda solo "los
  demás metadatos": el tokenizador de la Fase 2 trabaja sobre las llaves FITS originales
  (``tokenizar_header``) y DATE-OBS, como fecha de MongoDB, pierde decimales.

RA y DEC se guardan en grados, tal como vienen en el header, y **solo si están presentes**:
no se completan ni se imputan (según la ESO, su ausencia en calibraciones es válida;
Informe 1, sección 5.3, y reglas R3 y R5).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import HDFS_RAIZ


def ruta_hdfs(arcfile: str, date_obs: str, raiz: str = HDFS_RAIZ) -> str:
    """``/eso/xshooter/AAAA/MM/DD/<ARCFILE con ':' → '_'>``.

    Desviación respecto de la Figura 3 del Informe 1 (``hdfs_path`` conserva ``:``): HDFS
    rechaza ``:`` en los nombres (``InvalidPathException``). Ningún ARCFILE contiene ``_``,
    así que el reemplazo es inyectivo. La fecha sale de DATE-OBS (en los 1.861 archivos
    coincide con la del ARCFILE y con la del ZIP).
    """
    anio, mes, dia = date_obs[:4], date_obs[5:7], date_obs[8:10]
    return f"{raiz}/{anio}/{mes}/{dia}/{arcfile.replace(':', '_')}"


class DocumentoInvalido(ValueError):
    """El header no permite armar el documento; ``motivo`` es el de ``eso.revision``."""
    motivo = "header_invalido"


class SinArcfile(DocumentoInvalido):
    motivo = "sin_arcfile"  # R1: ARCFILE debe estar disponible


def _fecha_utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)


def validar_header(h: dict) -> tuple[str, str]:
    """R1 (ARCFILE disponible) y R2 (DATE-OBS válida). Devuelve ``(arcfile, date_obs)``."""
    arcfile = h.get("ARCFILE")
    if not isinstance(arcfile, str) or not arcfile.strip():
        raise SinArcfile("el header no tiene ARCFILE")
    date_obs = h.get("DATE-OBS")
    try:
        _fecha_utc(date_obs)
    except (TypeError, ValueError) as e:
        raise DocumentoInvalido(f"DATE-OBS inválida: {date_obs!r} ({e})") from None
    return arcfile, date_obs


def construir_documento(
    header: dict,
    *,
    source_zip: str,
    source_file: str,
    size_bytes: int,
    sha256: str | None = None,
    loaded_at: datetime | None = None,
) -> dict:
    h = header
    arcfile, _ = validar_header(h)

    search: dict = {"object": h.get("OBJECT")}
    # Coordenadas opcionales: se copian solo si el header las trae (sin null ni imputación).
    if "RA" in h:
        search["ra"] = h["RA"]
    if "DEC" in h:
        search["dec"] = h["DEC"]
    search["tiene_coordenadas"] = "RA" in h and "DEC" in h  # R3: RA y DEC como par
    search.update({
        "date_obs": _fecha_utc(h["DATE-OBS"]),
        "mjd_obs": h.get("MJD-OBS"),
        "exptime": h.get("EXPTIME"),
        "dpr": {"catg": h.get("ESO DPR CATG"), "type": h.get("ESO DPR TYPE"), "tech": h.get("ESO DPR TECH")},
        "program_id": h.get("ESO OBS PROG ID"),
        "instrument": h.get("INSTRUME"),
        "telescope": h.get("TELESCOP"),
        "indexado": True,  # Entrega 2: se indexan todas las categorías (aprobado)
    })
    storage = {
        "hdfs_path": ruta_hdfs(arcfile, h["DATE-OBS"]),
        "checksum": h.get("CHECKSUM"),
        "datasum": h.get("DATASUM"),
        "size_bytes": size_bytes,
        "sha256": sha256,
        "source": {"zip": source_zip, "file": source_file},
        "loaded_at": loaded_at or datetime.now(timezone.utc),
    }
    return {"_id": arcfile, "search": search, "storage": storage, "header": dict(h)}


# Índices de la Tabla 9 del Informe 1. El único sobre _id (ARCFILE) es automático.
INDICES_ENTREGA1 = [
    {"name": "date_obs", "keys": [("search.date_obs", 1)]},
    {"name": "object", "keys": [("search.object", 1)]},
    {"name": "ra_dec", "keys": [("search.ra", 1), ("search.dec", 1)]},
    {"name": "dpr_catg_type", "keys": [("search.dpr.catg", 1), ("search.dpr.type", 1)]},
]
# "Opcional" en la Tabla 9 ("si las consultas por programa son frecuentes"): ninguna de las
# consultas de prueba A–E filtra por programa, así que no se crea por defecto.
INDICES_OPCIONALES = [
    {"name": "program_id", "keys": [("search.program_id", 1)]},
]
