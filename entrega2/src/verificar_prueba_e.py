"""Verifica la Prueba E (RA ∈ [84, 85] y DEC ∈ [−70, −69]) en MongoDB.

1. Conjunto esperado, calculado desde ``/mnt/c/Bases/headers.csv`` (independiente de MongoDB).
2. Consulta en MongoDB con ``consultas.filtro_caja_coordenadas`` ($gte/$lte sobre search.ra y
   search.dec) y plan de ejecución: debe usar el índice compuesto ``ra_dec`` (IXSCAN).
3. Mismos ARCFILE en ambos, todos con RA y DEC dentro de la caja (y cuántos sobre un borde),
   ``search.ra``/``search.dec`` iguales a ``header.RA``/``header.DEC`` y ``tiene_coordenadas``.

Uso:
    python src/verificar_prueba_e.py [--esperados 18]
"""
from __future__ import annotations

import argparse
import csv
import sys

from pymongo import MongoClient

from config import HEADERS_CSV_REF, MONGO_COLECCION, MONGO_DB, MONGO_URI
from consultas import PRUEBA_E, filtro_caja_coordenadas


def esperados_desde_csv(caja: dict) -> dict[str, tuple[float, float]]:
    csv.field_size_limit(sys.maxsize)
    out = {}
    with open(HEADERS_CSV_REF, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["RA"] == "" or fila["DEC"] == "":
                continue
            ra, dec = float(fila["RA"]), float(fila["DEC"])
            if caja["ra_min"] <= ra <= caja["ra_max"] and caja["dec_min"] <= dec <= caja["dec_max"]:
                out[fila["ARCFILE"]] = (ra, dec)
    return out


def etapas(plan: dict) -> list[dict]:
    """Recorre el árbol del plan ganador (stage, inputStage, inputStages)."""
    salida, pila = [], [plan]
    while pila:
        p = pila.pop()
        salida.append(p)
        pila.extend(p.get("inputStages", []))
        if "inputStage" in p:
            pila.append(p["inputStage"])
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--esperados", type=int, default=18, help="resultado de la Fase 0")
    args = ap.parse_args()
    caja = PRUEBA_E
    filtro = filtro_caja_coordenadas(**caja)
    ok = True

    esperados = esperados_desde_csv(caja)
    print(f"Caja: RA [{caja['ra_min']}, {caja['ra_max']}] x DEC [{caja['dec_min']}, {caja['dec_max']}]")
    print(f"[1] Esperados desde headers.csv: {len(esperados)} (Fase 0: {args.esperados})")
    ok &= len(esperados) == args.esperados

    with MongoClient(MONGO_URI) as c:
        col = c[MONGO_DB][MONGO_COLECCION]
        print(f"[2] Filtro MongoDB: {filtro}")
        docs = list(col.find(filtro, {"search": 1, "header.RA": 1, "header.DEC": 1}))
        expl = col.find(filtro).explain()
    ganador = expl["queryPlanner"]["winningPlan"]
    ganador = ganador.get("queryPlan", ganador)  # motor SBE: el plan viene anidado
    st = expl["executionStats"]
    ixscans = [e for e in etapas(ganador) if e.get("stage") == "IXSCAN"]
    print(f"    plan ganador: {' <- '.join(e['stage'] for e in etapas(ganador))}; "
          f"índice: {[e.get('indexName') for e in ixscans]}; bounds: {[e.get('indexBounds') for e in ixscans]}")
    print(f"    nReturned={st['nReturned']}, totalKeysExamined={st['totalKeysExamined']}, "
          f"totalDocsExamined={st['totalDocsExamined']}, executionTimeMillis={st['executionTimeMillis']}")
    ok &= [e.get("indexName") for e in ixscans] == ["ra_dec"]

    obtenidos = {d["_id"]: d for d in docs}
    print(f"[3] Obtenidos de MongoDB: {len(obtenidos)}")
    faltan, sobran = sorted(set(esperados) - set(obtenidos)), sorted(set(obtenidos) - set(esperados))
    print(f"    faltan: {len(faltan)} {faltan[:3]} | sobran: {len(sobran)} {sobran[:3]}")
    ok &= not faltan and not sobran

    dentro = sum(caja["ra_min"] <= d["search"]["ra"] <= caja["ra_max"]
                 and caja["dec_min"] <= d["search"]["dec"] <= caja["dec_max"] for d in docs)
    estrictos = sum(caja["ra_min"] < d["search"]["ra"] < caja["ra_max"]
                    and caja["dec_min"] < d["search"]["dec"] < caja["dec_max"] for d in docs)
    iguales = sum(d["search"]["ra"] == d["header"]["RA"] and d["search"]["dec"] == d["header"]["DEC"] for d in docs)
    con_flag = sum(d["search"]["tiene_coordenadas"] is True for d in docs)
    ras = sorted(d["search"]["ra"] for d in docs)
    decs = sorted(d["search"]["dec"] for d in docs)
    print(f"    dentro de la caja (bordes incluidos): {dentro}/{len(docs)}; estrictamente dentro (sin tocar bordes): "
          f"{estrictos}/{len(docs)}")
    if docs:
        print(f"    RA observada [{ras[0]}, {ras[-1]}], DEC observada [{decs[0]}, {decs[-1]}]")
    print(f"    search.ra/dec == header.RA/DEC: {iguales}/{len(docs)}; tiene_coordenadas=true: {con_flag}/{len(docs)}")
    tipos = sorted({(d['search']['dpr']['catg'], d['search']['dpr']['type'], d['search']['object']) for d in docs})
    print(f"    (catg, type, object): {tipos}")
    ok &= dentro == iguales == con_flag == len(docs)  # "estrictos" es informativo: $gte/$lte incluye bordes

    print("RESULTADO:", "OK" if ok else "CON PROBLEMAS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
