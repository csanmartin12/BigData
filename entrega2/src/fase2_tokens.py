"""Fase 2: compara los modos de campos y regenera los artefactos del tokenizador.

1. Corpus desde MongoDB en los modos ``texto`` y ``todos``: tamaño del vocabulario, tokens por
   documento (mín/mediana/máx) y, para cada token de las 5 consultas, df global y cuántos
   documentos relevantes lo contienen (criterios de la Fase 0) →
   ``informe/df_tokens_consultas.csv`` (columna ``modo``) y ``informe/modos_campos.csv``.
2. Control: el tokenizador real aplicado a ``headers.csv`` (la fuente del prototipo), para
   separar las diferencias del tokenizador de las de la fuente de datos.
3. ``informe/llaves_con_guion_regla3.csv`` regenerado desde MongoDB.
4. Comparación con los archivos del prototipo (``informe/prototipo/``).

Uso:
    python src/fase2_tokens.py
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter, defaultdict

from config import COLUMNAS_CONTROL, ENTREGA2_DIR, HEADERS_CSV_REF
from consultas import CONSULTAS
from corpus import MODOS, construir_corpus, leer_headers_mongo
from tfidf import idf_de_termino
from tokenizer import _RE_FECHA_ISO, _RE_FRAGMENTO, clasificar_fragmento_guion, regla2_nulos, tokenizar, valor_a_texto

INFORME = ENTREGA2_DIR / "informe"
PROTOTIPO = INFORME / "prototipo"


def estadisticas_corpus(corpus) -> dict:
    largos = [len(t) for t in corpus.tokens]
    distintos = [len(set(t)) for t in corpus.tokens]
    vocab = {t for doc in corpus.tokens for t in doc}
    return {"modo": corpus.modo, "N": corpus.n, "vocabulario": len(vocab),
            "tokens_doc_min": min(largos), "tokens_doc_mediana": statistics.median(largos),
            "tokens_doc_max": max(largos), "distintos_doc_min": min(distintos),
            "distintos_doc_mediana": statistics.median(distintos), "distintos_doc_max": max(distintos),
            "tokens_totales": sum(largos)}


def filas_df_consultas(modo: str, docs_tokens: list[list[str]], headers: list[dict]) -> list[dict]:
    n = len(docs_tokens)
    conjuntos = [set(t) for t in docs_tokens]
    df = Counter(t for s in conjuntos for t in s)
    filas = []
    for cid, c in CONSULTAS.items():
        relevantes = [i for i, h in enumerate(headers) if c.es_relevante(h)]
        tokens = tokenizar(c.texto)
        base = {"modo": modo, "consulta": cid, "texto": c.texto, "criterio_relevancia": c.criterio,
                "n_relevantes": len(relevantes)}
        if not tokens:
            filas.append({**base, "token": "", "en_vocabulario": "", "df_global": "", "relevantes_con_token": "",
                          "N": n, "idf_suavizado_ln((1+N)/(1+df))+1": "", "idf_clasico_ln(N/df)": ""})
            continue
        for t in tokens:
            d = df.get(t, 0)
            clasico = idf_de_termino(d, n, "clasico")
            filas.append({**base, "token": t, "en_vocabulario": d > 0, "df_global": d,
                          "relevantes_con_token": sum(t in conjuntos[i] for i in relevantes), "N": n,
                          "idf_suavizado_ln((1+N)/(1+df))+1": round(idf_de_termino(d, n, "suavizado"), 6),
                          "idf_clasico_ln(N/df)": "" if clasico is None else round(clasico, 6)})
    return filas


def tokens_desde_csv() -> tuple[list[list[str]], list[dict]]:
    """Tokenizador real sobre headers.csv (celdas vacías = llave ausente, como NaN de pandas)."""
    csv.field_size_limit(sys.maxsize)
    docs, headers = [], []
    with open(HEADERS_CSV_REF, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            h = {k: v for k, v in fila.items() if k not in COLUMNAS_CONTROL and v != ""}
            t: list[str] = []
            for k, v in h.items():
                t.extend(tokenizar(v, llave=k))
            docs.append(t)
            # para el criterio numérico de la consulta E, RA/DEC del CSV pasan a float
            headers.append({**h, **{k: float(h[k]) for k in ("RA", "DEC") if k in h}})
    return docs, headers


def filas_guiones(docs: list[tuple[str, dict]]) -> list[dict]:
    """Pares (llave, valor) con un fragmento que tiene guion interno (no solo signo menos),
    sin contar las fechas ISO (se quitan antes, como en la regla 4); un registro por
    (llave, valor, fragmento), como el prototipo."""
    conteo: Counter = Counter()
    tipos: dict = {}
    for _id, h in docs:
        for k, v in h.items():
            texto = valor_a_texto(v)
            if "-" in texto:
                conteo[(k, texto)] += 1
                tipos[(k, texto)] = type(v).__name__
    filas = []
    for (k, texto), n in sorted(conteo.items()):
        sin_fechas = _RE_FECHA_ISO.sub(" ", regla2_nulos(texto))  # "excluidas las fechas" (regla 4)
        frags = [f for f in _RE_FRAGMENTO.findall(sin_fechas) if "-" in f[1:]]
        for f in dict.fromkeys(frags):
            filas.append({"llave": k, "valor": texto, "n_archivos": n, "fragmento_con_guion": f,
                          "clasificacion_regla3": clasificar_fragmento_guion(f),
                          "tokens_resultantes": " ".join(tokenizar(texto, llave=k)),
                          "tipo_valor": tipos[(k, texto)], "en_modo_texto": tipos[(k, texto)] == "str"})
    return filas


def escribir(ruta, filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"-> {ruta.relative_to(ENTREGA2_DIR)} ({len(filas)} filas)")


def leer(ruta) -> list[dict]:
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def comparar_df(prototipo: list[dict], nuevo: list[dict], etiqueta: str) -> None:
    clave = lambda r: (r["consulta"], r["token"])  # noqa: E731
    p = {clave(r): r for r in prototipo}
    cols = ["en_vocabulario", "df_global", "relevantes_con_token", "n_relevantes"]
    difs = []
    for r in nuevo:
        a = p.get(clave(r))
        if a is None:
            difs.append((clave(r), "no está en el prototipo"))
            continue
        for c in cols:
            if str(a[c]) != str(r[c]):
                difs.append((clave(r), f"{c}: prototipo={a[c]} nuevo={r[c]}"))
    print(f"  {etiqueta}: {len(nuevo)} filas comparadas, {len(difs)} diferencias")
    for d in difs:
        print("    ", d)


def main() -> None:
    docs = leer_headers_mongo()
    print(f"MongoDB: {len(docs)} headers")

    # 1. Modos de campos
    resumen, filas = [], []
    corpus_por_modo = {}
    for modo in MODOS:
        c = construir_corpus(modo, docs=docs)
        corpus_por_modo[modo] = c
        resumen.append(estadisticas_corpus(c))
        filas += filas_df_consultas(modo, c.tokens, c.headers)
    for r in resumen:
        print(r)
    # Qué se pierde en modo texto respecto de todos
    v_texto = {t for d in corpus_por_modo["texto"].tokens for t in d}
    v_todos = {t for d in corpus_por_modo["todos"].tokens for t in d}
    solo_todos = v_todos - v_texto
    numericos = {t for t in solo_todos if t.isdigit()}
    llaves_no_str = set()
    for _id, h in docs:
        for k, v in h.items():
            if not isinstance(v, str):
                llaves_no_str.update(tokenizar(None, llave=k))
    de_llaves = (solo_todos - numericos) & llaves_no_str
    print(f"Solo en modo todos: {len(solo_todos)} tokens; {len(numericos)} son solo dígitos "
          f"({100 * len(numericos) / len(solo_todos):.1f} %), {len(de_llaves)} vienen de llaves con valor no str "
          f"(p. ej. {sorted(de_llaves)[:8]}), resto {len(solo_todos - numericos - de_llaves)} "
          f"(p. ej. {sorted(solo_todos - numericos - de_llaves)[:8]})")
    print(f"Modo texto ⊂ modo todos: {v_texto <= v_todos}")
    escribir(INFORME / "modos_campos.csv", resumen)
    escribir(INFORME / "df_tokens_consultas.csv", filas)

    # 2. Control con headers.csv (fuente del prototipo)
    t_csv, h_csv = tokens_desde_csv()
    vocab_csv = {t for d in t_csv for t in d}
    filas_csv = filas_df_consultas("todos_desde_csv", t_csv, h_csv)
    print(f"Tokenizador real sobre headers.csv: vocabulario {len(vocab_csv)}")
    vocab_todos = {t for d in corpus_por_modo["todos"].tokens for t in d}
    print(f"  solo en CSV: {len(vocab_csv - vocab_todos)} {sorted(vocab_csv - vocab_todos)[:15]}")
    print(f"  solo en MongoDB(todos): {len(vocab_todos - vocab_csv)} {sorted(vocab_todos - vocab_csv)[:15]}")
    escribir(INFORME / "df_tokens_consultas_control_csv.csv", filas_csv)

    # 3. Guiones (regla 3)
    guiones = filas_guiones(docs)
    escribir(INFORME / "llaves_con_guion_regla3.csv", guiones)

    # 4. Comparación con el prototipo
    print("\nComparación con el prototipo (informe/prototipo/)")
    proto_df = leer(PROTOTIPO / "df_tokens_consultas.csv")
    comparar_df(proto_df, filas_csv, "control: tokenizador real sobre headers.csv")
    comparar_df(proto_df, [f for f in filas if f["modo"] == "todos"], "modo todos desde MongoDB")
    comparar_df(proto_df, [f for f in filas if f["modo"] == "texto"], "modo texto desde MongoDB")

    clave_g = lambda r: (r["llave"], r["valor"], r["fragmento_con_guion"])  # noqa: E731
    proto_g = {clave_g(r): r for r in leer(PROTOTIPO / "llaves_con_guion_regla3.csv")}
    nuevo_g = {clave_g(r): r for r in guiones}
    solo_p, solo_n = sorted(set(proto_g) - set(nuevo_g)), sorted(set(nuevo_g) - set(proto_g))
    distintos = defaultdict(list)
    for k in set(proto_g) & set(nuevo_g):
        for c in ("n_archivos", "clasificacion_regla3", "tokens_resultantes"):
            if str(proto_g[k][c]) != str(nuevo_g[k][c]):
                distintos[c].append((k, proto_g[k][c], nuevo_g[k][c]))
    print(f"  llaves_con_guion_regla3: prototipo {len(proto_g)} filas ({len({k[0] for k in proto_g})} llaves), "
          f"nuevo {len(nuevo_g)} filas ({len({k[0] for k in nuevo_g})} llaves)")
    print(f"    solo en el prototipo: {len(solo_p)} {solo_p[:5]}")
    print(f"    solo en el nuevo: {len(solo_n)} {solo_n[:5]}")
    for c, v in distintos.items():
        print(f"    {c} distinto en {len(v)}: {v[:3]}")
    print(f"    filas del nuevo por tipo de valor: {Counter(r['tipo_valor'] for r in guiones)}; "
          f"en modo texto: {sum(r['en_modo_texto'] for r in guiones)}")


if __name__ == "__main__":
    main()
