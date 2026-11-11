import zipfile
import json
import io
from pathlib import Path
from datetime import datetime, timezone

from astropy.io import fits
import pandas as pd

RAW_DIR = Path("./rars")         
OUT_CSV = Path("./headers.csv")
OUT_LOG = Path("./headers_log.jsonl")


def log(entry: dict, logfile=OUT_LOG):
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def extraer_header(zip_path: Path, member_name: str) -> dict | None:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            raw_bytes = zf.read(member_name)          
        with fits.open(io.BytesIO(raw_bytes), memmap=False) as hdul:
            hdr = dict(hdul[0].header)                 # solo el header
        hdr["_source_zip"] = zip_path.name
        hdr["_source_file"] = member_name
        return hdr
    except Exception as e:
        log({"zip": zip_path.name, "file": member_name, "status": "ERROR", "error": str(e)})
        return None


def main():
    zips = sorted(RAW_DIR.glob("XSHOO.*.zip"))
    if not zips:
        raise SystemExit(f"No se encontraron zips en {RAW_DIR.resolve()}")

    log({"status": "INICIO", "n_zips": len(zips), "zips": [z.name for z in zips]})

    total_ok, total_err = 0, 0
    rows = [] 

    for zip_path in zips:
        with zipfile.ZipFile(zip_path) as zf:
            members = [n for n in zf.namelist() if n.lower().endswith(".fits")]

        print(f"{zip_path.name}: {len(members)} archivos .fits")
        for i, member in enumerate(members, 1):
            hdr = extraer_header(zip_path, member)
            if hdr is not None:
                rows.append(hdr)
                total_ok += 1
            else:
                total_err += 1

            if i % 100 == 0:
                print(f"  ...{i}/{len(members)} procesados")

        log({"status": "ZIP_COMPLETADO", "zip": zip_path.name, "n_procesados": len(members)})

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)

    log({"status": "FIN", "total_ok": total_ok, "total_error": total_err,
         "n_columnas": df.shape[1], "n_filas": df.shape[0], "archivo_salida": str(OUT_CSV)})

    print(f"\nListo. {total_ok} headers extraídos, {total_err} errores.")
    print(f"Tabla consolidada: {OUT_CSV} ({df.shape[0]} filas x {df.shape[1]} columnas)")
    print(f"Log de proceso: {OUT_LOG}")


if __name__ == "__main__":
    main()
