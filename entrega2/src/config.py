"""Rutas y parámetros compartidos por la Entrega 2.

Todas las rutas se pueden sobreescribir con variables de entorno, pero por defecto apuntan
al equipo de medición (notebook, WSL2): los datos de la Entrega 1 están en ``C:\\Bases`` y se
leen desde WSL2 como ``/mnt/c/Bases``.
"""
import os
from pathlib import Path

# Insumos de la Entrega 1 (solo lectura)
DATA_DIR = Path(os.environ.get("ENTREGA2_DATA_DIR", "/mnt/c/Bases"))
HEADERS_CSV_REF = DATA_DIR / "headers.csv"
ZIP_GLOB = "XSHOO.*.zip"

# Proyecto
ENTREGA2_DIR = Path(__file__).resolve().parent.parent
SALIDAS_DIR = Path(os.environ.get("ENTREGA2_SALIDAS_DIR", ENTREGA2_DIR / "salidas"))

# Servicios (docker compose en infra/; puertos publicados en localhost)
MONGO_URI = os.environ.get("ENTREGA2_MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("ENTREGA2_MONGO_DB", "eso")
MONGO_COLECCION = os.environ.get("ENTREGA2_MONGO_COLECCION", "xshooter")
# R1/R6 (Informe 1, Tabla 11): archivos separados para revisión en lugar de eliminarse
MONGO_REVISION = os.environ.get("ENTREGA2_MONGO_REVISION", "revision")

WEBHDFS_URL = os.environ.get("ENTREGA2_WEBHDFS_URL", "http://localhost:9870/webhdfs/v1")
HDFS_USUARIO = os.environ.get("ENTREGA2_HDFS_USUARIO", "hadoop")
HDFS_RAIZ = os.environ.get("ENTREGA2_HDFS_RAIZ", "/eso/xshooter")
HDFS_REVISION = os.environ.get("ENTREGA2_HDFS_REVISION", "/eso/revision")

# Hilos de BLAS del buscador (METODOLOGIA.md, Fase 6, "Sonda previa"): con los 14 hilos por
# defecto, un producto matriz-vector de 1.861 × 2.497 es 3–4 veces más lento que con 1.
HILOS_BLAS = int(os.environ.get("ENTREGA2_HILOS_BLAS", "1"))

# Columnas de control de headers.csv (posiciones 439–442 en base 0, tras las 439 llaves del
# primer archivo)
COLUMNAS_CONTROL = ["_n_campos_header", "_n_campos_sin_info", "_source_zip", "_source_file"]


def listar_zips(data_dir: Path = DATA_DIR) -> list[Path]:
    """Los ZIP de la Entrega 1 en orden alfabético."""
    return sorted(data_dir.glob(ZIP_GLOB))
