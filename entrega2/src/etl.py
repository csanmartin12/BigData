"""ETL de la Fase 1 con PySpark: ZIP → documento → MongoDB + FITS a HDFS, con las reglas R1/R6.

Qué corre dónde:

- **Driver** (este proceso): lee solo el *directorio central* de cada ZIP (nombres y tamaños;
  ningún byte de FITS). Si un ZIP está tan dañado que no se puede listar, lo registra en
  ``eso.revision`` (R6) y sigue con los demás. Reparte los miembros en particiones equilibradas
  por bytes, lanza el job, recibe una métrica por partición y crea los índices.
- **Tareas de Spark** (workers de Python de los ejecutores), una por partición y todas con
  ``mapPartitions``:
  1. ``extraer``: lee cada FITS completo desde el ZIP, su header primario y su SHA-256. Si algo
     falla (miembro dañado, header corrupto, sin END) produce un registro de revisión (R6) en
     lugar de abortar.
  2. ``transformar``: valida ARCFILE (R1) y DATE-OBS (R2) y arma el documento ``search`` /
     ``storage`` / ``header``.
  3. ``cargar`` (``carga.py``): R1 — reclama el ARCFILE en MongoDB (``insert_one``; el índice
     único de ``_id`` arbitra) y solo entonces sube el FITS por WebHDFS a
     ``/eso/xshooter/AAAA/MM/DD/<ARCFILE con ':' → '_'>``. Si el ARCFILE ya existe con el mismo
     SHA-256 se omite; si existe con otro, va a ``eso.revision`` (``conflicto_arcfile``) sin
     tocar la ruta principal. También escribe los registros de revisión de las etapas
     anteriores. Devuelve las métricas de la partición.
  Spark encadena las etapas en el mismo worker de Python, sin copiar los bytes entre etapas.

Uso:
    python src/etl.py --zips XSHOO.2026-09-07.zip --limpiar   # prueba con 1 ZIP
    python src/etl.py --limpiar --etiqueta completo_1         # los 6 ZIP, desde cero
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

from carga import (  # noqa: E402
    ERROR_HDFS, ILEGIBLE, INSERTADO, OMITIDO_IDENTICO, cargar_documento, registrar_revision, texto_error,
)
from config import (  # noqa: E402
    DATA_DIR, HDFS_RAIZ, HDFS_REVISION, MONGO_COLECCION, MONGO_DB, MONGO_REVISION, MONGO_URI, SALIDAS_DIR,
    listar_zips,
)
from documento import INDICES_ENTREGA1, DocumentoInvalido, construir_documento  # noqa: E402
from entorno import condiciones_validas, resumen_equipo  # noqa: E402
from fits_header import leer_header_bytes, miembros_fits  # noqa: E402


# ---------------------------------------------------------------------------
# Driver: plan de tareas (solo metadatos de los ZIP)
# ---------------------------------------------------------------------------
def planificar(zips: list[Path]) -> tuple[list[dict], list[dict]]:
    """``(tareas, zips_ilegibles)``. Un ZIP que no se puede listar no detiene el plan (R6)."""
    tareas, ilegibles = [], []
    for zp in zips:
        try:
            with zipfile.ZipFile(zp) as zf:  # lee el directorio central, no los FITS
                for info in miembros_fits(zf):
                    tareas.append({"zip": str(zp), "zip_name": zp.name, "miembro": info.filename,
                                   "tamano": info.file_size, "comprimido": info.compress_size})
        except Exception as e:  # noqa: BLE001
            ilegibles.append({"zip_name": zp.name, "error": texto_error(e)})
    return tareas, ilegibles


def repartir(tareas: list[dict], n: int) -> list[list[dict]]:
    """Reparte las tareas en ``n`` grupos de tamaño (bytes) parecido (mayor primero)."""
    n = max(1, min(n, len(tareas)))
    grupos: list[list[dict]] = [[] for _ in range(n)]
    heap = [(0, i) for i in range(n)]
    for t in sorted(tareas, key=lambda t: -t["tamano"]):
        carga, i = heapq.heappop(heap)
        grupos[i].append(t)
        heapq.heappush(heap, (carga + t["tamano"], i))
    for g in grupos:  # dentro de cada grupo, en orden del ZIP (lectura más secuencial)
        g.sort(key=lambda t: (t["zip_name"], t["miembro"]))
    return grupos


# ---------------------------------------------------------------------------
# Tareas de Spark (se ejecutan en los workers de Python, una partición por tarea)
# ---------------------------------------------------------------------------
def _revision(motivo, etapa, t, error, m, datos=None, sha256=None, arcfile=None, **extra):
    return {"tipo": "revision", "motivo": motivo, "etapa": etapa, "tarea": t, "error": error, "m": m,
            "datos": datos, "sha256": sha256, "arcfile": arcfile, **extra}


def extraer(particion):
    """[lista de tareas] → registros ``ok`` (header, bytes, sha256) o ``revision`` (R6)."""
    for tareas in particion:  # cada partición trae un solo elemento: su lista de tareas
        abiertos: dict[str, zipfile.ZipFile] = {}
        try:
            for t in tareas:
                m: dict = {}
                t0 = time.perf_counter()
                try:
                    zf = abiertos.get(t["zip"])
                    if zf is None:
                        zf = abiertos[t["zip"]] = zipfile.ZipFile(t["zip"])
                    datos = zf.read(t["miembro"])  # verifica el CRC-32 del miembro
                except Exception as e:  # noqa: BLE001 — R6: ZIP o miembro dañado
                    m["t_extraer"] = time.perf_counter() - t0
                    yield _revision(ILEGIBLE, "leer_zip", t, texto_error(e), m)
                    continue
                error = None
                try:
                    header = leer_header_bytes(datos)
                except Exception as e:  # noqa: BLE001 — R6: header corrupto, sin END, no FITS
                    error = texto_error(e)
                m["t_extraer"] = time.perf_counter() - t0
                t0 = time.perf_counter()
                sha = hashlib.sha256(datos).hexdigest()
                m["t_sha256"] = time.perf_counter() - t0
                if error:
                    yield _revision(ILEGIBLE, "leer_header", t, error, m, datos=datos, sha256=sha)
                    continue
                yield {"tipo": "ok", "tarea": t, "header": header, "datos": datos, "sha256": sha, "m": m}
        finally:
            for zf in abiertos.values():
                zf.close()


def transformar(particion):
    for r in particion:
        if r["tipo"] == "ok":
            t0 = time.perf_counter()
            t = r["tarea"]
            try:
                r["doc"] = construir_documento(r["header"], source_zip=t["zip_name"], source_file=t["miembro"],
                                               size_bytes=len(r["datos"]), sha256=r["sha256"])
            except DocumentoInvalido as e:  # R1 (sin ARCFILE) / R2 (DATE-OBS inválida)
                r = _revision(e.motivo, "transformar", t, texto_error(e), r["m"], datos=r["datos"],
                              sha256=r["sha256"], arcfile=r["header"].get("ARCFILE"))
            r["m"]["t_transformar"] = time.perf_counter() - t0
        yield r


def cargar(particion):
    """R1 + carga en MongoDB/HDFS + registros de revisión; devuelve las métricas de la partición."""
    from pymongo import MongoClient
    from pyspark import TaskContext

    from hdfs_webhdfs import WebHDFS

    tc = TaskContext.get()  # solo existe dentro de una tarea de Spark
    inicio = time.time()
    agg = {"n": 0, "insertados": 0, "omitidos_identicos": 0, "revision": Counter(), "bytes_subidos": 0,
           "t_extraer": 0.0, "t_sha256": 0.0, "t_transformar": 0.0, "t_mongo": 0.0, "t_hdfs": 0.0,
           "t_revision": 0.0, "pid": os.getpid(),
           "tarea": {"stage": tc.stageId(), "particion": tc.partitionId(), "intento": tc.attemptNumber(),
                     "task_attempt_id": tc.taskAttemptId()}}
    cliente = MongoClient(MONGO_URI)
    col = cliente[MONGO_DB][MONGO_COLECCION]
    rev = cliente[MONGO_DB][MONGO_REVISION]
    hdfs = WebHDFS()  # uno por partición

    def a_revision(r):
        t0 = time.perf_counter()
        t = r["tarea"]
        registrar_revision(rev, hdfs, motivo=r["motivo"], etapa=r["etapa"], zip_name=t["zip_name"],
                           miembro=t["miembro"], error=r.get("error"), arcfile=r.get("arcfile"),
                           sha256=r.get("sha256"), datos=r.get("datos"),
                           sha256_existente=r.get("sha256_existente"))
        agg["revision"][r["motivo"]] += 1
        agg["t_revision"] += time.perf_counter() - t0

    try:
        for r in particion:
            agg["n"] += 1
            for k, v in r["m"].items():
                agg[k] += v
            if r["tipo"] == "revision":
                a_revision(r)
                continue
            doc = r["doc"]
            resultado, detalle = cargar_documento(doc, r["datos"], col, hdfs, tiempos=agg)
            if resultado == INSERTADO:
                agg["insertados"] += 1
                agg["bytes_subidos"] += doc["storage"]["size_bytes"]
            elif resultado == OMITIDO_IDENTICO:
                agg["omitidos_identicos"] += 1
            else:  # CONFLICTO_ARCFILE o ERROR_HDFS
                a_revision(_revision(resultado, "cargar", r["tarea"], detalle.get("error"), r["m"],
                                     datos=r["datos"], sha256=r["sha256"], arcfile=doc["_id"],
                                     sha256_existente=detalle.get("sha256_existente")))
    finally:
        cliente.close()
    agg["revision"] = dict(agg["revision"])
    agg["inicio"], agg["fin"] = inicio, time.time()
    yield agg


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def _jmx(url: str, qry: str) -> dict:
    import requests
    beans = requests.get(url, params={"qry": qry}, timeout=10).json()["beans"]
    return beans[0] if beans else {}


def limpiar_destinos(espera_max_s: int = 180) -> dict:
    """Vacía las colecciones principal y de revisión y sus raíces de HDFS, y espera a que el
    datanode borre los bloques (borrado asíncrono). Queda fuera del tiempo medido."""
    from pymongo import MongoClient

    from hdfs_webhdfs import WebHDFS
    t0 = time.perf_counter()
    with MongoClient(MONGO_URI) as c:
        c[MONGO_DB][MONGO_COLECCION].drop()
        c[MONGO_DB][MONGO_REVISION].drop()
    h = WebHDFS()
    for raiz in (HDFS_RAIZ, HDFS_REVISION):
        if h.estado(raiz) is not None:
            h.borrar(raiz)
    nn = dn = {}
    while time.perf_counter() - t0 < espera_max_s:
        nn = _jmx("http://localhost:9870/jmx", "Hadoop:service=NameNode,name=FSNamesystem")
        dn = _jmx("http://localhost:9864/jmx", "Hadoop:service=DataNode,name=FSDatasetState*")
        # Lo que queda en HDFS (otras raíces) más ~0,8 % de archivos .meta de checksums y margen
        restante = (h.resumen("/") or {}).get("spaceConsumed", 0)
        if nn.get("PendingDeletionBlocks") == 0 and dn.get("DfsUsed", 0) < 1.01 * restante + 50e6:
            break
        time.sleep(2)
    estado = {"segundos": round(time.perf_counter() - t0, 1), "BlocksTotal": nn.get("BlocksTotal"),
              "PendingDeletionBlocks": nn.get("PendingDeletionBlocks"), "DfsUsed_datanode": dn.get("DfsUsed")}
    print(f"Destinos vaciados: {MONGO_DB}.{{{MONGO_COLECCION},{MONGO_REVISION}}} y "
          f"hdfs:{{{HDFS_RAIZ},{HDFS_REVISION}}} {estado}")
    return estado


def crear_indices() -> list[str]:
    from pymongo import MongoClient
    with MongoClient(MONGO_URI) as c:
        col = c[MONGO_DB][MONGO_COLECCION]
        for ix in INDICES_ENTREGA1:
            col.create_index(ix["keys"], name=ix["name"])
        return sorted(col.index_information())


def registrar_zips_ilegibles(ilegibles: list[dict]) -> None:
    from pymongo import MongoClient
    with MongoClient(MONGO_URI) as c:
        rev = c[MONGO_DB][MONGO_REVISION]
        for z in ilegibles:
            registrar_revision(rev, None, motivo=ILEGIBLE, etapa="listar_zip", zip_name=z["zip_name"],
                               miembro=None, error=z["error"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zips", nargs="*", help="nombres de ZIP a procesar (por defecto, todos)")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--hilos", default="*", help="núcleos de Spark: local[HILOS] (por defecto *)")
    ap.add_argument("--particiones-por-hilo", type=int, default=3)
    ap.add_argument("--limpiar", action="store_true",
                    help="vacía eso.xshooter, eso.revision, hdfs:/eso/xshooter y hdfs:/eso/revision antes")
    ap.add_argument("--etiqueta", default="", help="texto libre para el archivo de métricas")
    args = ap.parse_args()

    equipo = resumen_equipo()
    equipo["condiciones_validas"] = condiciones_validas(equipo["energia"])
    print("Equipo:", json.dumps(equipo["energia"], ensure_ascii=False))
    if not equipo["condiciones_validas"]:
        print("AVISO: no está enchufado en \"Máximo rendimiento\"; esta medición no vale para el informe.")

    zips = listar_zips(args.data_dir)
    if args.zips:
        zips = [z for z in zips if z.name in set(args.zips)]
        faltan = set(args.zips) - {z.name for z in zips}
        if faltan:
            raise SystemExit(f"ZIP inexistentes: {sorted(faltan)}")
    limpieza = limpiar_destinos() if args.limpiar else None

    # ---- desde aquí se mide ----
    t_total = time.perf_counter()
    t0 = time.perf_counter()
    tareas, zips_ilegibles = planificar(zips)
    t_plan = time.perf_counter() - t0
    bytes_total = sum(t["tamano"] for t in tareas)
    print(f"Plan (driver): {len(zips)} ZIP ({len(zips_ilegibles)} ilegibles), {len(tareas)} FITS, "
          f"{bytes_total / 1e6:,.1f} MB sin comprimir "
          f"({sum(t['comprimido'] for t in tareas) / 1e6:,.1f} MB comprimidos) en {t_plan:.2f} s")
    if zips_ilegibles:
        registrar_zips_ilegibles(zips_ilegibles)
        for z in zips_ilegibles:
            print(f"  R6: ZIP ilegible -> eso.{MONGO_REVISION}: {z}")
    if not tareas:
        raise SystemExit("No hay FITS que procesar")

    # Los workers de Python heredan este entorno: importan los módulos de src/ y usan el venv.
    os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SRC), os.environ.get("PYTHONPATH")]))
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    from pyspark.sql import SparkSession

    t0 = time.perf_counter()
    spark = (SparkSession.builder.master(f"local[{args.hilos}]").appName("entrega2-etl-fase1")
             .config("spark.ui.showConsoleProgress", "false")
             .config("spark.driver.memory", "2g")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    sc = spark.sparkContext
    t_spark = time.perf_counter() - t0
    hilos = sc.defaultParallelism
    grupos = repartir(tareas, hilos * args.particiones_por_hilo)
    print(f"Spark {spark.version} {sc.master}: {hilos} hilos, {len(grupos)} particiones "
          f"({args.particiones_por_hilo} por hilo; arranque {t_spark:.1f} s)")

    t0 = time.perf_counter()
    metricas = (sc.parallelize(grupos, len(grupos))   # 1 elemento (lista de tareas) por partición
                .mapPartitions(extraer)               # tarea de Spark: ZIP -> (header, bytes) | revisión (R6)
                .mapPartitions(transformar)           # tarea de Spark: header -> documento | revisión (R1/R2)
                .mapPartitions(cargar)                # tarea de Spark: R1 en MongoDB -> FITS a HDFS | revisión
                .collect())                           # driver: solo 1 dict de métricas por partición
    t_etl = time.perf_counter() - t0
    spark.stop()

    t0 = time.perf_counter()
    indices = crear_indices()
    t_indices = time.perf_counter() - t0
    t_total = time.perf_counter() - t_total
    # ---- fin de lo medido ----

    # Evidencia de que el trabajo ocurrió en tareas de Spark y no en el driver
    pid_driver = os.getpid()
    particiones_vistas = sorted(m["tarea"]["particion"] for m in metricas)
    en_tareas = all(m["pid"] != pid_driver for m in metricas) and particiones_vistas == list(range(len(grupos)))
    pids = sorted({m["pid"] for m in metricas})

    n = sum(m["n"] for m in metricas)
    insertados = sum(m["insertados"] for m in metricas)
    omitidos = sum(m["omitidos_identicos"] for m in metricas)
    revision = Counter()
    for m in metricas:
        revision.update(m["revision"])
    revision_zip = len(zips_ilegibles)
    etapas = {k: sum(m[k] for m in metricas)
              for k in ("t_extraer", "t_sha256", "t_transformar", "t_mongo", "t_hdfs", "t_revision")}
    suma_etapas = sum(etapas.values()) or 1.0
    print(f"\nETL: {n} FITS, {bytes_total / 1e6:,.1f} MB en {t_etl:.1f} s de pared "
          f"({bytes_total / 1e6 / t_etl:,.1f} MB/s, {n / t_etl:.1f} FITS/s)")
    print(f"Carga (R1/R6): insertados {insertados}, omitidos por duplicado idéntico {omitidos}, "
          f"a revisión {sum(revision.values())} {dict(revision)}"
          + (f" + {revision_zip} ZIP ilegible(s)" if revision_zip else ""))
    print(f"Tareas: {len(metricas)} particiones en el stage {sorted({m['tarea']['stage'] for m in metricas})}, "
          f"{len(pids)} workers de Python (pid del driver {pid_driver}, no aparece: {en_tareas})")
    print("Tiempo sumado en los workers por etapa:")
    for k, v in etapas.items():
        print(f"  {k[2:]:<12} {v:8.1f} s  ({100 * v / suma_etapas:4.1f} %)")
    print(f"Índices ({t_indices:.1f} s): {indices}")
    print(f"Total medido (plan + arranque Spark + ETL + índices): {t_total:.1f} s")

    cuadra = n == len(tareas) == insertados + omitidos + sum(revision.values())
    SALIDAS_DIR.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    salida = SALIDAS_DIR / f"etl_{marca}{'_' + args.etiqueta if args.etiqueta else ''}.json"
    salida.write_text(json.dumps({
        "fecha_utc": marca, "etiqueta": args.etiqueta, "version_etl": "r1r6", "equipo": equipo,
        "limpieza": limpieza, "zips": [z.name for z in zips], "zips_ilegibles": zips_ilegibles,
        "n_fits": n, "bytes": bytes_total,
        "carga": {"insertados": insertados, "omitidos_identicos": omitidos, "revision": dict(revision),
                  "revision_total": sum(revision.values()), "zips_ilegibles": revision_zip,
                  "bytes_subidos": sum(m["bytes_subidos"] for m in metricas)},
        "spark": {"version": spark.version, "master": f"local[{args.hilos}]", "hilos": hilos,
                  "particiones": len(grupos), "pid_driver": pid_driver, "pids_workers": pids,
                  "trabajo_en_tareas_spark": en_tareas},
        "tiempos_s": {"plan": t_plan, "arranque_spark": t_spark, "etl": t_etl, "indices": t_indices, "total": t_total},
        "etapas_suma_workers_s": etapas, "particiones": metricas, "indices": indices,
    }, indent=2, ensure_ascii=False))
    print(f"Métricas: {salida}")
    if not cuadra or not en_tareas:
        raise SystemExit(f"ERROR: {len(tareas)} FITS planificados; procesados {n}, insertados+omitidos+revisión "
                         f"{insertados + omitidos + sum(revision.values())}, en_tareas={en_tareas}")


if __name__ == "__main__":
    main()
