"""Verifica un headers.csv regenerado contra el de referencia de la Entrega 1.

Comprobaciones (todas sobre el texto de cada celda, sin reinterpretar tipos):

1. Dimensiones: 1.861 filas × 685 columnas en ambos.
2. Mismas columnas en el mismo orden; las 4 columnas de control en las posiciones 439–442
   (base 0; 440–443 en base 1).
3. Filas ordenadas por ZIP y, dentro de cada ZIP, por archivo; misma secuencia en ambos.
4. Comparación celda por celda.

Termina con código 1 si hay cualquier diferencia.

Uso:
    python src/verificar_headers.py salidas/headers_regenerado.csv [--referencia /mnt/c/Bases/headers.csv]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from config import COLUMNAS_CONTROL, HEADERS_CSV_REF

FILAS_ESPERADAS = 1861
COLUMNAS_ESPERADAS = 685
POSICIONES_CONTROL = [439, 440, 441, 442]  # base 0


def leer_csv(ruta: Path) -> tuple[list[str], list[list[str]]]:
    csv.field_size_limit(sys.maxsize)
    with open(ruta, newline="", encoding="utf-8") as f:
        lector = csv.reader(f)
        columnas = next(lector)
        return columnas, list(lector)


def verificar(generado: Path, referencia: Path, max_ejemplos: int = 10) -> bool:
    ok = True

    def falla(msg: str) -> None:
        nonlocal ok
        ok = False
        print("  FALLA:", msg)

    cols_g, filas_g = leer_csv(generado)
    cols_r, filas_r = leer_csv(referencia)
    print(f"Referencia: {referencia} ({len(filas_r)} x {len(cols_r)})")
    print(f"Generado:   {generado} ({len(filas_g)} x {len(cols_g)})")

    print("[1] Dimensiones")
    for nombre, cols, filas in (("referencia", cols_r, filas_r), ("generado", cols_g, filas_g)):
        if (len(filas), len(cols)) != (FILAS_ESPERADAS, COLUMNAS_ESPERADAS):
            falla(f"{nombre}: {len(filas)} x {len(cols)} (se esperaba {FILAS_ESPERADAS} x {COLUMNAS_ESPERADAS})")
        anchos = {len(f) for f in filas}
        if anchos != {len(cols)}:
            falla(f"{nombre}: filas con distinto número de celdas {sorted(anchos)}")

    print("[2] Columnas y posiciones de control")
    if cols_g != cols_r:
        solo_r = [c for c in cols_r if c not in set(cols_g)]
        solo_g = [c for c in cols_g if c not in set(cols_r)]
        primera = next((i for i, (a, b) in enumerate(zip(cols_r, cols_g)) if a != b), None)
        falla(f"columnas distintas: solo en referencia {solo_r[:5]}, solo en generado {solo_g[:5]}, "
              f"primer desorden en la posición {primera}")
    for nombre, cols in (("referencia", cols_r), ("generado", cols_g)):
        pos = [cols.index(c) if c in cols else None for c in COLUMNAS_CONTROL]
        if pos != POSICIONES_CONTROL:
            falla(f"{nombre}: columnas de control en {pos}, se esperaba {POSICIONES_CONTROL}")

    print("[3] Orden de filas (ZIP, archivo)")
    for nombre, cols, filas in (("referencia", cols_r, filas_r), ("generado", cols_g, filas_g)):
        iz, ia = cols.index("_source_zip"), cols.index("_source_file")
        claves = [(f[iz], f[ia]) for f in filas]
        if claves != sorted(claves):
            falla(f"{nombre}: filas no ordenadas por (ZIP, archivo)")
        if len(set(claves)) != len(claves):
            falla(f"{nombre}: hay (ZIP, archivo) repetidos")
    iz_r, ia_r = cols_r.index("_source_zip"), cols_r.index("_source_file")
    iz_g, ia_g = cols_g.index("_source_zip"), cols_g.index("_source_file")
    if [(f[iz_r], f[ia_r]) for f in filas_r] != [(f[iz_g], f[ia_g]) for f in filas_g]:
        falla("la secuencia de (ZIP, archivo) difiere entre referencia y generado")

    print("[4] Celda por celda")
    if not ok:
        print("  (se omite: las estructuras no coinciden)")
        return False
    n_celdas = 0
    difs = []
    for i, (fr, fg) in enumerate(zip(filas_r, filas_g)):
        for j, (vr, vg) in enumerate(zip(fr, fg)):
            n_celdas += 1
            if vr != vg:
                difs.append((i, cols_r[j], fr[ia_r], vr, vg))
    miles = lambda n: f"{n:,}".replace(",", ".")  # noqa: E731
    print(f"  {miles(n_celdas)} celdas comparadas; {miles(len(difs))} diferencias")
    vacias = sum(v == "" for f in filas_r for v in f)
    print(f"  (celdas vacías en la referencia: {miles(vacias)}; llave ausente y valor '' se escriben igual)")
    for i, col, archivo, vr, vg in difs[:max_ejemplos]:
        print(f"    fila {i} ({archivo}) [{col}]: referencia={vr!r} generado={vg!r}")
    if difs:
        falla(f"{len(difs)} celdas distintas")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("generado", type=Path)
    ap.add_argument("--referencia", type=Path, default=HEADERS_CSV_REF)
    args = ap.parse_args()
    ok = verificar(args.generado, args.referencia)
    print("RESULTADO:", "IDÉNTICO" if ok else "CON DIFERENCIAS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
