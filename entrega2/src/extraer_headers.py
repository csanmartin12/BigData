"""Regenera headers.csv desde los ZIP de la Entrega 1.

Reemplaza la lógica de ``/mnt/c/Bases/extraer_headers.py`` (que no se modifica) con las
reglas de METODOLOGIA.md: excluir COMMENT/HISTORY/CONTINUE, una ocurrencia por llave e
ignorar ``__MACOSX/`` y ``._*``. Lee solo los headers (no descomprime las imágenes).

Uso:
    python src/extraer_headers.py [--salida salidas/headers_regenerado.csv]
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from config import DATA_DIR, SALIDAS_DIR, listar_zips
from fits_header import contar_sin_info, iterar_headers_zip


def fila_csv(header: dict, zip_name: str, miembro: str) -> dict:
    """Header + las 4 columnas de control, en el orden de headers.csv."""
    fila = dict(header)
    fila["_n_campos_header"] = len(header)
    fila["_n_campos_sin_info"] = contar_sin_info(header)
    fila["_source_zip"] = zip_name
    fila["_source_file"] = miembro
    return fila


def extraer_filas(zips: list[Path]) -> list[dict]:
    filas = []
    for zp in zips:  # ZIP en orden alfabético; miembros en orden alfabético (miembros_fits)
        for miembro, header in iterar_headers_zip(zp):
            filas.append(fila_csv(header, zp.name, miembro))
    return filas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--salida", type=Path, default=SALIDAS_DIR / "headers_regenerado.csv")
    args = ap.parse_args()

    zips = listar_zips(args.data_dir)
    if not zips:
        raise SystemExit(f"No hay ZIP en {args.data_dir}")
    t0 = time.perf_counter()
    filas = extraer_filas(zips)
    # Columnas en orden de primera aparición (como pd.DataFrame(list_of_dicts) en la Entrega 1)
    df = pd.DataFrame(filas)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.salida, index=False)
    print(f"{len(zips)} ZIP, {df.shape[0]} filas x {df.shape[1]} columnas en "
          f"{time.perf_counter() - t0:.1f} s -> {args.salida}")


if __name__ == "__main__":
    main()
