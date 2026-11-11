"""Conteos de la Fase 1 en MongoDB y HDFS, con verificación cruzada.

- MongoDB: documentos totales, por categoría (DPR CATG), por ZIP, con coordenadas; índices.
- HDFS: archivos, directorios y bytes bajo /eso/xshooter; archivos por día; replicación.
- Cruce: cada ``storage.hdfs_path`` de MongoDB existe en HDFS con el mismo tamaño y no sobra
  ningún archivo en HDFS. Opcionalmente descarga una muestra y compara el SHA-256.

Uso:
    python src/conteos.py [--muestra-sha 10] [--esperados 1861]
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
from collections import Counter

from pymongo import MongoClient

from config import HDFS_RAIZ, HDFS_REVISION, MONGO_COLECCION, MONGO_DB, MONGO_REVISION, MONGO_URI
from hdfs_webhdfs import WebHDFS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--muestra-sha", type=int, default=10, help="FITS a descargar de HDFS para comparar SHA-256")
    ap.add_argument("--esperados", type=int, default=None, help="número de FITS esperado (p. ej. 1861)")
    args = ap.parse_args()
    ok = True

    with MongoClient(MONGO_URI) as cliente:
        col = cliente[MONGO_DB][MONGO_COLECCION]
        n_docs = col.count_documents({})
        por_catg = {d["_id"]: d["n"] for d in col.aggregate([
            {"$group": {"_id": "$search.dpr.catg", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])}
        por_zip = {d["_id"]: d["n"] for d in col.aggregate([
            {"$group": {"_id": "$storage.source.zip", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])}
        con_coord = col.count_documents({"search.tiene_coordenadas": True})
        sin_coord = col.count_documents({"search.tiene_coordenadas": False})
        con_ra = col.count_documents({"search.ra": {"$exists": True}})
        con_dec = col.count_documents({"search.dec": {"$exists": True}})
        ra_null = col.count_documents({"search.ra": None})  # null o ausente
        indexados = col.count_documents({"search.indexado": True})
        stats = next(col.aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
        indices = col.index_information()
        rev = cliente[MONGO_DB][MONGO_REVISION]
        n_rev = rev.count_documents({})
        rev_por_motivo = {d["_id"]: d["n"] for d in rev.aggregate([
            {"$group": {"_id": "$motivo", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])}
        docs = {d["_id"]: d["storage"] for d in col.find({}, {"storage.hdfs_path": 1, "storage.size_bytes": 1,
                                                             "storage.sha256": 1})}

    print(f"MongoDB {MONGO_DB}.{MONGO_COLECCION}")
    print(f"  documentos: {n_docs}")
    print(f"  por ESO DPR CATG: {por_catg}")
    print(f"  por ZIP: {por_zip}")
    print(f"  search.tiene_coordenadas: true {con_coord}, false {sin_coord}; "
          f"con search.ra {con_ra}, con search.dec {con_dec}, sin search.ra {ra_null}")
    print(f"  search.indexado = true: {indexados}")
    print(f"  tamaño: {stats['size'] / 1e6:.1f} MB de datos sin comprimir, "
          f"promedio {stats.get('avgObjSize', 0) / 1e3:.1f} kB/documento, "
          f"{stats['storageSize'] / 1e6:.1f} MB en disco + {stats['totalIndexSize'] / 1e6:.2f} MB de índices")
    print(f"  índices ({len(indices)}):")
    for nombre, info in indices.items():
        print(f"    {nombre}: {info['key']}")

    print(f"\nMongoDB {MONGO_DB}.{MONGO_REVISION} (R1/R6): {n_rev} {rev_por_motivo}")

    h = WebHDFS()
    resumen_rev = h.resumen(HDFS_REVISION)
    print(f"HDFS {HDFS_REVISION}: {resumen_rev['fileCount'] if resumen_rev else 0} archivos")
    resumen = h.resumen(HDFS_RAIZ)
    archivos = h.listar_recursivo(HDFS_RAIZ)
    print(f"\nHDFS {HDFS_RAIZ}")
    if resumen is None:
        print("  (no existe)")
        archivos = []
    else:
        print(f"  archivos: {resumen['fileCount']}, directorios: {resumen['directoryCount']}, "
              f"bytes: {resumen['length']:,} ({resumen['length'] / 1e9:.2f} GB), "
              f"espacio ocupado: {resumen['spaceConsumed']:,}")
        por_dia = Counter("/".join(r.split("/")[3:6]) for r, _ in archivos)
        print(f"  por día (AAAA/MM/DD): {dict(sorted(por_dia.items()))}")
        print(f"  replicación: {dict(Counter(st['replication'] for _, st in archivos))}")

    print("\nVerificación cruzada")
    en_hdfs = {r: st["length"] for r, st in archivos}
    rutas_mongo = {s["hdfs_path"]: (i, s["size_bytes"]) for i, s in docs.items()}
    faltan = sorted(set(rutas_mongo) - set(en_hdfs))
    sobran = sorted(set(en_hdfs) - set(rutas_mongo))
    tam_mal = sorted(r for r in set(rutas_mongo) & set(en_hdfs) if rutas_mongo[r][1] != en_hdfs[r])
    print(f"  documentos sin archivo en HDFS: {len(faltan)} {faltan[:3]}")
    print(f"  archivos en HDFS sin documento: {len(sobran)} {sobran[:3]}")
    print(f"  tamaños distintos: {len(tam_mal)} {tam_mal[:3]}")
    ok &= not (faltan or sobran or tam_mal)
    if args.esperados is not None:
        cuadra = n_docs == len(en_hdfs) == args.esperados
        print(f"  esperados {args.esperados}: MongoDB {n_docs}, HDFS {len(en_hdfs)} -> {'OK' if cuadra else 'NO CUADRA'}")
        ok &= cuadra

    if args.muestra_sha and docs:
        muestra = random.Random(0).sample(sorted(docs), min(args.muestra_sha, len(docs)))
        malos = 0
        for arc in muestra:
            r = h.s.get(h.url + docs[arc]["hdfs_path"], params=h._params("OPEN"))
            r.raise_for_status()
            malos += hashlib.sha256(r.content).hexdigest() != docs[arc]["sha256"]
        print(f"  SHA-256 de {len(muestra)} FITS descargados de HDFS: {len(muestra) - malos} coinciden, {malos} no")
        ok &= malos == 0

    print("\nRESULTADO:", "OK" if ok else "CON PROBLEMAS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
