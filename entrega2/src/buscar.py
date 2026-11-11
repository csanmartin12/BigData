"""CLI del buscador híbrido de FITS X-shooter (Fase 5).

Ejemplos:
    python src/buscar.py --texto "filt b"                                   # solo semántica
    python src/buscar.py --ra-min 84 --ra-max 85 --dec-min -70 --dec-max -69  # solo numérica (Prueba E)
    python src/buscar.py --texto "flat sky" --fecha-desde 2026-09-05 --fecha-hasta 2026-09-05 \\
                         --modelo lsi --optim kmeans                         # combinada

Salida: rango, puntaje (coseno) y ``storage.hdfs_path`` desde MongoDB, más los tokens fuera del
vocabulario y los avisos. ``--json`` imprime el resultado completo en JSON. No usa HDFS.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from buscador import MODELOS, OPTIMIZACIONES, Buscador  # noqa: E402


def argumentos(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--texto", help="consulta en texto libre (misma tokenización que los documentos)")
    ap.add_argument("--modelo", choices=MODELOS, default="tfidf")
    ap.add_argument("--optim", choices=OPTIMIZACIONES, default="ninguna")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--n-probe", type=int, default=1, help="clústeres a revisar con --optim kmeans (1 por defecto)")
    ap.add_argument("--fecha-desde", help="DATE-OBS desde (AAAA-MM-DD o ISO con hora, UTC)")
    ap.add_argument("--fecha-hasta", help="DATE-OBS hasta (AAAA-MM-DD = hasta el final de ese día)")
    for c in ("ra", "dec", "exptime"):
        ap.add_argument(f"--{c}-min", type=float)
        ap.add_argument(f"--{c}-max", type=float)
    ap.add_argument("--categoria", help="ESO DPR CATG: CALIB, SCIENCE, ACQUISITION, …")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = argumentos(argv)
    filtros = {k: getattr(a, k) for k in ("fecha_desde", "fecha_hasta", "ra_min", "ra_max", "dec_min", "dec_max",
                                         "exptime_min", "exptime_max", "categoria")}
    t0 = time.perf_counter()
    b = Buscador()
    t_carga = time.perf_counter() - t0
    try:
        t0 = time.perf_counter()
        r = b.buscar(a.texto, a.modelo, a.optim, a.top, a.n_probe, **filtros)
        t_busqueda = time.perf_counter() - t0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        b.cerrar()
    if a.json:
        print(json.dumps({**r.a_dict(), "modelo": a.modelo, "optim": a.optim,
                          "tiempos_s": {"carga_indices": t_carga, "busqueda": t_busqueda}}, ensure_ascii=False))
        return 0
    print(f"Consulta {r.modo} | modelo {a.modelo} | optim {a.optim} | top {a.top}")
    if r.tokens:
        print(f"Tokens: {r.tokens}  fuera del vocabulario: {r.fuera_de_vocabulario or 'ninguno'}")
    if r.filtro_mongo:
        print(f"Filtro MongoDB: {r.n_candidatos_filtro} candidatos")
    if r.n_examinados is not None:
        print(f"Documentos con coseno exacto: {r.n_examinados}")
    for aviso in r.avisos:
        print(f"AVISO: {aviso}")
    for i, x in enumerate(r.resultados, 1):
        puntaje = "" if x["puntaje"] is None else f"{x['puntaje']:.4f}  "
        print(f"{i:>4}. {puntaje}{x['hdfs_path']}")
    print(f"({len(r.resultados)} resultados; carga de índices {t_carga:.2f} s, búsqueda {1000 * t_busqueda:.1f} ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
