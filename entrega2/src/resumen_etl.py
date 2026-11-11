"""Resume las corridas del ETL completo (salidas/etl_*_completo_*.json): tabla y mediana.

Escribe ``informe/etl_tiempos.csv``. La primera corrida se marca como "caché fría": la VM de
WSL2 no retiene los ZIP en caché (lectura por 9P, ver METODOLOGIA.md), pero la caché de
archivos de Windows sí puede retener parte de ellos para las corridas siguientes.

Uso:
    python src/resumen_etl.py [--patron 'etl_*_completo_v2_*.json'] [--salida informe/etl_tiempos.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from config import ENTREGA2_DIR, SALIDAS_DIR


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patron", default="etl_*_completo_v2_*.json")
    ap.add_argument("--salida", default=str(ENTREGA2_DIR / "informe" / "etl_tiempos.csv"))
    args = ap.parse_args()
    archivos = sorted(SALIDAS_DIR.glob(args.patron))  # orden por fecha (nombre empieza con la marca UTC)
    filas = []
    for i, a in enumerate(archivos, 1):
        d = json.loads(a.read_text())
        t, e = d["tiempos_s"], d["etapas_suma_workers_s"]
        en = d["equipo"]["energia"]
        filas.append({
            "corrida": i,
            "cache": "fría" if i == 1 else "tibia",
            "fecha_utc": d["fecha_utc"],
            "n_fits": d["n_fits"],
            "mb": round(d["bytes"] / 1e6, 1),
            "plan_s": round(t["plan"], 2),
            "arranque_spark_s": round(t["arranque_spark"], 2),
            "etl_s": round(t["etl"], 2),
            "indices_s": round(t["indices"], 2),
            "total_s": round(t["total"], 2),
            "mb_por_s": round(d["bytes"] / 1e6 / t["etl"], 1),
            "fits_por_s": round(d["n_fits"] / t["etl"], 1),
            "insertados": d.get("carga", {}).get("insertados", d["n_fits"]),
            "omitidos_identicos": d.get("carga", {}).get("omitidos_identicos", 0),
            "revision": d.get("carga", {}).get("revision_total", 0),
            "extraer_pct": round(100 * e["t_extraer"] / sum(e.values()), 1),
            "hdfs_pct": round(100 * e["t_hdfs"] / sum(e.values()), 1),
            "particiones": d["spark"]["particiones"],
            "workers_python": len(d["spark"]["pids_workers"]),
            "en_tareas_spark": d["spark"]["trabajo_en_tareas_spark"],
            "en_corriente": en.get("en_corriente"),
            "modo_ac": en.get("modo_ac"),
            "condiciones_validas": d["equipo"].get("condiciones_validas"),
            "standby_windows_mb": d["equipo"].get("memoria_windows", {}).get("standby_mb"),
            "archivo": a.name,
        })
    if not filas:
        raise SystemExit(f"No hay archivos {args.patron} en {SALIDAS_DIR}")

    cols = ["corrida", "cache", "etl_s", "total_s", "mb_por_s", "fits_por_s", "arranque_spark_s",
            "insertados", "omitidos_identicos", "revision", "extraer_pct", "hdfs_pct", "standby_windows_mb",
            "condiciones_validas"]
    print(" | ".join(cols))
    for f in filas:
        print(" | ".join(str(f[c]) for c in cols))
    med = {c: statistics.median(f[c] for f in filas) for c in ("etl_s", "total_s", "mb_por_s", "fits_por_s")}
    print(f"MEDIANA ({len(filas)} corridas): ETL {med['etl_s']:.2f} s, total {med['total_s']:.2f} s, "
          f"{med['mb_por_s']:.1f} MB/s, {med['fits_por_s']:.1f} FITS/s")
    etl = [f["etl_s"] for f in filas]
    print(f"Rango ETL: {min(etl):.2f}–{max(etl):.2f} s (amplitud {max(etl) - min(etl):.2f} s, "
          f"{100 * (max(etl) - min(etl)) / med['etl_s']:.1f} % de la mediana)")

    salida = Path(args.salida)
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
        w.writerow({"corrida": "mediana", **{k: round(v, 2) for k, v in med.items()}})
    print(f"-> {salida}")


if __name__ == "__main__":
    main()
