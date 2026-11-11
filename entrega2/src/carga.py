"""Reglas de ingesta R1 y R6 del Informe 1 (Tabla 11), usadas en la etapa de carga del ETL.

- **R1**: el ARCFILE debe estar disponible y no puede chocar con otro archivo ya registrado que
  tenga información distinta.
  * Mismo ARCFILE y mismo SHA-256 → se **omite** (carga idempotente).
  * Mismo ARCFILE y otro SHA-256 → **no se sobrescribe**: el archivo nuevo va a
    ``eso.revision`` con motivo ``conflicto_arcfile`` y su FITS **no** se sube a la ruta
    principal de HDFS.
- **R6**: un archivo que no se puede leer (ZIP dañado, header corrupto, sin END, sin ARCFILE,
  DATE-OBS inválida) no detiene el job: se registra en ``eso.revision`` con el ZIP, el miembro
  y el error, y el resto continúa.

Para que nada se elimine (R6 dice "se separan para revisión en lugar de eliminarse"), si hay
bytes disponibles se guarda una copia en ``/eso/revision/<sha256>.fits``, fuera de la ruta
principal. Usar el SHA-256 como nombre evita colisiones y hace idempotente la copia.

**Cómo se decide el ARCFILE sin carreras**: primero se *reclama* el ``_id`` con ``insert_one``
(el índice único de ``_id`` lo arbitra, incluso entre tareas de Spark concurrentes) y solo quien
lo reclamó sube el FITS a la ruta principal. Si la subida falla, se libera el reclamo
(``delete_one``) y el archivo va a revisión con motivo ``error_hdfs``.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from config import HDFS_REVISION

INSERTADO = "insertado"
OMITIDO_IDENTICO = "omitido_identico"
CONFLICTO_ARCFILE = "conflicto_arcfile"
ILEGIBLE = "ilegible"
SIN_ARCFILE = "sin_arcfile"
HEADER_INVALIDO = "header_invalido"
ERROR_HDFS = "error_hdfs"
MOTIVOS_REVISION = (CONFLICTO_ARCFILE, ILEGIBLE, SIN_ARCFILE, HEADER_INVALIDO, ERROR_HDFS)


def texto_error(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


def cargar_documento(doc: dict, datos: bytes, col, hdfs, tiempos: dict | None = None) -> tuple[str, dict]:
    """Aplica R1 a un documento ya transformado. Devuelve ``(resultado, detalle)``.

    ``col`` es la colección principal (API de pymongo) y ``hdfs`` un ``WebHDFS`` (o un doble de
    prueba con ``crear``).
    """
    tiempos = tiempos if tiempos is not None else {}
    sha = doc["storage"]["sha256"]
    for _ in range(2):  # 2.º intento solo si el dueño del _id lo liberó entre medio
        t0 = time.perf_counter()
        try:
            col.insert_one(doc)  # reclama el ARCFILE
            reclamado = True
        except DuplicateKeyError:
            reclamado = False
            existente = col.find_one({"_id": doc["_id"]}, {"storage.sha256": 1})
        tiempos["t_mongo"] = tiempos.get("t_mongo", 0.0) + time.perf_counter() - t0
        if reclamado:
            break
        if existente is None:
            continue
        sha_existente = existente["storage"]["sha256"]
        if sha_existente == sha:
            return OMITIDO_IDENTICO, {}
        return CONFLICTO_ARCFILE, {"sha256_existente": sha_existente}
    else:
        raise RuntimeError(f"no se pudo reclamar {doc['_id']!r}")

    t0 = time.perf_counter()
    try:
        hdfs.crear(doc["storage"]["hdfs_path"], datos, sobrescribir=True)
    except Exception as e:  # noqa: BLE001 — R6: no detener el job
        col.delete_one({"_id": doc["_id"], "storage.sha256": sha})  # libera el reclamo
        return ERROR_HDFS, {"error": texto_error(e)}
    finally:
        tiempos["t_hdfs"] = tiempos.get("t_hdfs", 0.0) + time.perf_counter() - t0
    return INSERTADO, {}


def id_revision(motivo: str, zip_name: str | None, miembro: str | None, sha256: str | None) -> str:
    """Id determinista: volver a ejecutar el ETL no duplica entradas de revisión."""
    return "|".join([motivo, zip_name or "-", miembro or "-", sha256 or "-"])


def registrar_revision(rev, hdfs, *, motivo: str, etapa: str, zip_name: str | None, miembro: str | None,
                       error: str | None = None, arcfile: str | None = None, sha256: str | None = None,
                       datos: bytes | None = None, sha256_existente: str | None = None,
                       revision_raiz: str = HDFS_REVISION) -> dict:
    """Guarda el caso en ``eso.revision`` (upsert por id determinista) y, si hay bytes, una
    copia del FITS en ``<revision_raiz>/<sha256>.fits``. Devuelve el documento de revisión."""
    if motivo not in MOTIVOS_REVISION:
        raise ValueError(f"motivo desconocido: {motivo}")
    doc = {
        "_id": id_revision(motivo, zip_name, miembro, sha256),
        "motivo": motivo,
        "etapa": etapa,
        "zip": zip_name,
        "miembro": miembro,
        "error": error,
        "arcfile": arcfile,
        "sha256": sha256,
        "sha256_existente": sha256_existente,
        "size_bytes": len(datos) if datos is not None else None,
        "revision_hdfs_path": None,
        "detectado_en": datetime.now(timezone.utc),
    }
    if datos is not None and sha256 and hdfs is not None:
        ruta = f"{revision_raiz}/{sha256}.fits"
        try:
            hdfs.crear(ruta, datos, sobrescribir=True)
            doc["revision_hdfs_path"] = ruta
        except Exception as e:  # noqa: BLE001
            doc["error_copia_hdfs"] = texto_error(e)
    rev.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return doc
