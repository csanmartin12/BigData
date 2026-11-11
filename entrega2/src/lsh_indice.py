"""LSH con hiperplanos aleatorios (SimHash, coseno) para la búsqueda aproximada (Fase 4B).

- Hiperplanos: **solo** ``numpy.random.default_rng(20261111).normal(0, 1, (L, b, d))``.
- A mano:
  * firma de x en la tabla l: bit j = 1 si ``H[l, j] · x ≥ 0`` (0 en otro caso); los b bits se
    empaquetan en un entero ``Σ_j bit_j · 2^j``;
  * L tablas de buckets: diccionario firma → arreglo de documentos;
  * consulta: unión de los buckets de su firma en las L tablas; si quedan **menos de K
    candidatos** (filtros y exclusiones incluidos), multi-probe con las firmas a distancia de
    Hamming 1 y, si aún faltan, a distancia 2; luego re-ranking por coseno exacto sobre los
    candidatos.
- Espacios: TF-IDF (2.497 dimensiones) y LSI (14). La firma no depende de la escala del vector.
- Fase 4b: radio máximo de multi-probe configurable (Hamming 1 … radio, sin pasar de b) y
  **centrado** opcional: se resta el vector medio del corpus (``Σ x_i / N`` de los vectores de
  norma 1, a mano) a documentos y consultas antes de ``H·x``. Solo cambia las firmas; el
  reranking usa el coseno exacto del espacio original.

Uso (barrido de validación + persistencia del elegido):
    python src/lsh_indice.py [--solo-grafico]
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

SEMILLA_LSH = 20261111
BITS = (4, 8, 12, 16)          # grilla de la primera validación
TABLAS = (1, 4, 8, 16)
BITS_V2 = (2, 4, 8, 12, 16)    # grilla de la Fase 4b
RADIOS_V2 = (2, 3, 4)
CENTRADO_V2 = (False, True)
K_POR_DEFECTO = 10
_MASCARAS: dict[tuple[int, int], list[int]] = {}


def mascaras(n_bits: int, distancia: int) -> list[int]:
    """Máscaras XOR con exactamente ``distancia`` bits encendidos (a mano, con caché)."""
    clave = (n_bits, distancia)
    if clave not in _MASCARAS:
        _MASCARAS[clave] = [sum(1 << j for j in c) for c in combinations(range(n_bits), distancia)]
    return _MASCARAS[clave]


def vector_medio(x: np.ndarray) -> np.ndarray:
    """Media de las filas, a mano: Σ x_i / N."""
    suma = np.zeros(x.shape[1])
    for fila in x:
        suma += fila
    return suma / x.shape[0]


def generar_hiperplanos(n_tablas: int, n_bits: int, dim: int, semilla: int = SEMILLA_LSH) -> np.ndarray:
    """Única función base permitida: normales estándar con semilla fija."""
    return np.random.default_rng(semilla).normal(0.0, 1.0, size=(n_tablas, n_bits, dim))


def empaquetar(bits: np.ndarray) -> np.ndarray:
    """``(..., b)`` booleanos → enteros ``Σ_j bit_j · 2^j`` (a mano, sin ``packbits``)."""
    pesos = np.array([1 << j for j in range(bits.shape[-1])], dtype=np.int64)
    return (bits.astype(np.int64) * pesos).sum(axis=-1)


@dataclass
class IndiceLSH:
    espacio: str
    hiperplanos: np.ndarray        # L × b × d
    firmas: np.ndarray             # L × N (enteros)
    buckets: list[dict] = field(repr=False)  # por tabla: firma → arreglo de documentos
    media: np.ndarray | None = None          # vector medio restado antes de H·x (centrado)
    radio_max: int = 2                       # radio máximo de multi-probe

    @property
    def n_tablas(self) -> int:
        return self.hiperplanos.shape[0]

    @property
    def n_bits(self) -> int:
        return self.hiperplanos.shape[1]

    def firma(self, x: np.ndarray) -> np.ndarray:
        """Firma (una por tabla) de un vector o de una matriz de vectores por fila → L o N × L."""
        if self.media is not None:
            x = x - self.media
        proy = np.einsum("lbd,...d->...lb", self.hiperplanos, x)
        return empaquetar(proy >= 0)

    def _vecinos(self, s: int, distancia: int):
        for m in mascaras(self.n_bits, distancia):
            yield s ^ m

    def candidatos(self, q: np.ndarray, k: int = K_POR_DEFECTO, permitidos: np.ndarray | None = None,
                   excluir: int | None = None, radio: int | None = None) -> tuple[np.ndarray, dict]:
        """Unión de buckets; multi-probe (Hamming 1, 2, … hasta ``radio``) si hay menos de ``k``.

        ``permitidos``: máscara booleana (N) del filtro de MongoDB; ``excluir``: documento a sacar;
        ``radio``: radio máximo (por defecto el del índice), sin pasar de b.
        """
        radio = self.radio_max if radio is None else radio
        fq = self.firma(q)
        trozos: list[np.ndarray] = []
        sondas = 0

        def filtrar() -> np.ndarray:
            c = np.unique(np.concatenate(trozos)) if trozos else np.empty(0, np.int64)
            if permitidos is not None:
                c = c[permitidos[c]]
            if excluir is not None:
                c = c[c != excluir]
            return c

        for l in range(self.n_tablas):
            sondas += 1
            b = self.buckets[l].get(int(fq[l]))
            if b is not None:
                trozos.append(b)
        cand, nivel = filtrar(), 0
        for distancia in range(1, min(radio, self.n_bits) + 1):
            if cand.size >= k:
                break
            for l in range(self.n_tablas):
                for s in self._vecinos(int(fq[l]), distancia):
                    sondas += 1
                    b = self.buckets[l].get(s)
                    if b is not None:
                        trozos.append(b)
            cand, nivel = filtrar(), distancia
        return cand, {"nivel_multiprobe": nivel, "buckets_sondeados": sondas}


def construir(espacio: str, x: np.ndarray, n_bits: int, n_tablas: int, semilla: int = SEMILLA_LSH,
              centrado: bool = False, radio_max: int = 2) -> IndiceLSH:
    h = generar_hiperplanos(n_tablas, n_bits, x.shape[1], semilla)
    media = vector_medio(x) if centrado else None
    tmp = IndiceLSH(espacio, h, np.empty((n_tablas, 0), np.int64), [], media, radio_max)
    firmas = tmp.firma(x).T  # L × N
    buckets = []
    for l in range(n_tablas):
        d: dict[int, list[int]] = {}
        for i, s in enumerate(firmas[l]):
            d.setdefault(int(s), []).append(i)
        buckets.append({s: np.array(v, dtype=np.int64) for s, v in d.items()})
    return IndiceLSH(espacio, h, firmas, buckets, media, radio_max)


def grupos_identicos(x: np.ndarray) -> np.ndarray:
    """Id de grupo por documento: mismo id ⇔ vector idéntico (bit a bit)."""
    ids: dict[bytes, int] = {}
    return np.array([ids.setdefault(fila.tobytes(), len(ids)) for fila in x], dtype=np.int64)


def grupos_casi_identicos(x_tfidf, df: np.ndarray) -> np.ndarray:
    """Grupos de documentos iguales salvo términos con df = 1 (en este corpus, el nombre de
    archivo de ORIGFILE, único por documento): se comparan las columnas con df > 1."""
    sub = x_tfidf[:, np.flatnonzero(df > 1)]
    sub = sub.toarray() if hasattr(sub, "toarray") else sub
    return grupos_identicos(np.ascontiguousarray(sub))


def colision_de_grupos(firmas: np.ndarray, grupos: np.ndarray) -> dict:
    """Fracción de pares de un mismo grupo que comparten bucket: por tabla (media) y en ≥ 1 tabla."""
    pares = mismo_por_tabla = alguna = 0
    for g in np.flatnonzero(np.bincount(grupos) > 1):
        m = np.flatnonzero(grupos == g)
        f = firmas[:, m]  # L × |g|
        for a, b in combinations(range(m.size), 2):
            iguales = f[:, a] == f[:, b]
            pares += 1
            mismo_por_tabla += iguales.mean()
            alguna += bool(iguales.any())
    return {"pares": pares, "mismo_bucket_por_tabla": mismo_por_tabla / pares if pares else float("nan"),
            "mismo_bucket_en_alguna_tabla": alguna / pares if pares else float("nan")}


def estadisticas(ix: IndiceLSH, grupos: np.ndarray, grupos_casi: np.ndarray | None = None) -> dict:
    tam = np.concatenate([np.array([len(v) for v in t.values()]) for t in ix.buckets])
    n = ix.firmas.shape[1]
    conteo_grupos = np.bincount(grupos)
    en_grupo = conteo_grupos[grupos] > 1
    # ¿todos los miembros de cada grupo idéntico comparten firma en todas las tablas?
    colisionan = all(len({tuple(ix.firmas[:, i]) for i in np.flatnonzero(grupos == g)}) == 1
                     for g in np.flatnonzero(conteo_grupos > 1))
    mayor = max((v for t in ix.buckets for v in t.values()), key=len)
    return {"buckets_por_tabla_media": float(np.mean([len(t) for t in ix.buckets])),
            "bucket_min": int(tam.min()), "bucket_mediana": float(np.median(tam)), "bucket_max": int(tam.max()),
            "bucket_media": float(tam.mean()), "fraccion_bucket_mayor": float(tam.max() / n),
            "vectores_distintos_en_bucket_mayor": int(np.unique(grupos[mayor]).size),
            "grupos_identicos": int((conteo_grupos > 1).sum()), "docs_en_grupos_identicos": int(en_grupo.sum()),
            "grupo_identico_mayor": int(conteo_grupos.max()), "identicos_siempre_colisionan": bool(colisionan),
            **({} if grupos_casi is None else {
                "grupos_casi_identicos": int((np.bincount(grupos_casi) > 1).sum()),
                "docs_casi_identicos": int((np.bincount(grupos_casi)[grupos_casi] > 1).sum()),
                **{f"casi_identicos_{k}": v for k, v in colision_de_grupos(ix.firmas, grupos_casi).items()}})}


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def guardar(ix: IndiceLSH, directorio) -> list[str]:
    pref = f"lsh_{ix.espacio}"
    np.save(directorio / f"{pref}_hiperplanos.npy", ix.hiperplanos)
    np.save(directorio / f"{pref}_firmas.npy", ix.firmas)
    arreglos = {}
    for l, t in enumerate(ix.buckets):
        claves = np.array(sorted(t), dtype=np.int64)
        tam = np.array([len(t[c]) for c in claves], dtype=np.int64)
        arreglos[f"t{l}_firmas"] = claves
        arreglos[f"t{l}_indptr"] = np.concatenate([[0], np.cumsum(tam)]).astype(np.int64)
        arreglos[f"t{l}_docs"] = np.concatenate([t[c] for c in claves]).astype(np.int64)
    np.savez(directorio / f"{pref}_buckets.npz", **arreglos)
    archivos = [f"{pref}_hiperplanos.npy", f"{pref}_firmas.npy", f"{pref}_buckets.npz"]
    media = directorio / f"{pref}_media.npy"
    if ix.media is not None:
        np.save(media, ix.media)
        archivos.append(media.name)
    elif media.exists():
        media.unlink()  # de una elección anterior con centrado
    return archivos


def cargar(directorio, espacio: str, radio_max: int | None = None, centrado: bool | None = None) -> IndiceLSH:
    """Lee el índice; radio y centrado salen del manifiesto si no se indican."""
    import json
    pref = f"lsh_{espacio}"
    if radio_max is None or centrado is None:
        ruta_man = directorio / "manifiesto.json"
        meta = (json.loads(ruta_man.read_text()).get("lsh", {}).get("espacios", {}).get(espacio, {})
                if ruta_man.exists() else {})
        radio_max = meta.get("radio_max", 2) if radio_max is None else radio_max
        centrado = meta.get("centrado", (directorio / f"{pref}_media.npy").exists()) if centrado is None else centrado
    h = np.load(directorio / f"{pref}_hiperplanos.npy")
    firmas = np.load(directorio / f"{pref}_firmas.npy")
    z = np.load(directorio / f"{pref}_buckets.npz")
    buckets = []
    for l in range(h.shape[0]):
        claves, indptr, docs = z[f"t{l}_firmas"], z[f"t{l}_indptr"], z[f"t{l}_docs"]
        buckets.append({int(c): docs[indptr[i]:indptr[i + 1]] for i, c in enumerate(claves)})
    media = np.load(directorio / f"{pref}_media.npy") if centrado else None
    return IndiceLSH(espacio, h, firmas, buckets, media, radio_max)


# ---------------------------------------------------------------------------
# Barrido de validación (Fase 4b): consultas cortas = oficial; documentos = secundario
# ---------------------------------------------------------------------------
CSV_V2 = "validacion_v2_lsh.csv"
CLAVES_DESEMPATE = ("memoria_Lb", "radio_max", "centrado")


def _es_verdad(v) -> bool:
    return v is True or str(v) == "True"


def graficar_v2(filas: list[dict], elegidos: dict) -> None:
    from config import ENTREGA2_DIR
    from graficos import nube_costo_recall
    from validacion import UMBRAL_RECALL
    paneles = []
    for n in ("tfidf", "lsi"):
        fs = [f for f in filas if f["espacio"] == n and f["conjunto"] == "cortas"]
        series = [{"nombre": "centrado" if cen else "sin centrar",
                   "x": [float(f["costo"]) for f in fs if _es_verdad(f["centrado"]) == cen],
                   "y": [float(f["recall_tolerante"]) for f in fs if _es_verdad(f["centrado"]) == cen]}
                  for cen in CENTRADO_V2]
        e = elegidos[n]
        texto = (f"elegido: b={e['n_bits']}, L={e['n_tablas']}, radio {e['radio_max']}, "
                 f"{'centrado' if _es_verdad(e['centrado']) else 'sin centrar'}")
        paneles.append({"titulo": f"Espacio {n.upper()}", "series": series,
                        "elegido": {"x": float(e["costo"]), "y": float(e["recall_tolerante"]), "texto": texto}})
    nube_costo_recall(paneles, ENTREGA2_DIR / "informe" / "validacion_cortas_lsh.png", UMBRAL_RECALL,
                      "LSH: costo vs. recall relativo — 200 consultas cortas (120 configuraciones por espacio)")


def solo_grafico() -> None:
    import json

    import indice as indice_mod
    from config import ENTREGA2_DIR
    filas = list(csv.DictReader(open(ENTREGA2_DIR / "informe" / CSV_V2, encoding="utf-8")))
    man = json.loads((indice_mod.INDICE_DIR / "manifiesto.json").read_text())["lsh"]["espacios"]
    elegidos = {n: next(f for f in filas if f["espacio"] == n and f["conjunto"] == "cortas"
                        and int(f["n_bits"]) == man[n]["n_bits"] and int(f["n_tablas"]) == man[n]["n_tablas"]
                        and int(f["radio_max"]) == man[n]["radio_max"] and _es_verdad(f["centrado"]) == man[n]["centrado"])
                for n in ("tfidf", "lsi")}
    graficar_v2(filas, elegidos)


def en_borde(f: dict) -> list[str]:
    bordes = []
    if f["n_bits"] in (min(BITS_V2), max(BITS_V2)):
        bordes.append(f"b = {f['n_bits']}")
    if f["n_tablas"] in (min(TABLAS), max(TABLAS)):
        bordes.append(f"L = {f['n_tablas']}")
    if f["radio_max"] in (min(RADIOS_V2), max(RADIOS_V2)):
        bordes.append(f"radio = {f['radio_max']}")
    return bordes


def main() -> None:
    import conjuntos
    import indice as indice_mod
    from config import ENTREGA2_DIR
    from espacios import ESPACIOS, espacios_desde_indice
    from validacion import elegir, evaluar_de, linea_base_de

    informe = ENTREGA2_DIR / "informe"
    t_inicio = time.perf_counter()
    ix = indice_mod.cargar()
    esp = espacios_desde_indice(ix)
    conj, _, est_cortas = conjuntos.preparar(ix, esp)
    print(f"Consultas cortas: {est_cortas}")
    grupos_casi = grupos_casi_identicos(ix.tfidf.matriz, ix.tfidf.df)
    filas, elegidos, motivos, secundarios = [], {}, {}, {}
    for nombre in ESPACIOS:
        e = esp[nombre]
        lbs = {c: linea_base_de(e, conj[nombre][c]) for c in ("cortas", "documentos")}
        grupos = grupos_identicos(e.x)
        for centrado in CENTRADO_V2:
            for b in BITS_V2:
                for n_tablas in TABLAS:
                    t0 = time.perf_counter()
                    lsh = construir(nombre, e.x, b, n_tablas, centrado=centrado, radio_max=max(RADIOS_V2))
                    t_construir = time.perf_counter() - t0
                    est = estadisticas(lsh, grupos, grupos_casi)
                    for radio in RADIOS_V2:
                        for cj, lb in lbs.items():
                            def cand(j, q, excl, lsh=lsh, radio=radio):
                                c, info = lsh.candidatos(q, K_POR_DEFECTO, excluir=excl, radio=radio)
                                return c, {"nivel_multiprobe": info["nivel_multiprobe"],
                                           "buckets_sondeados": info["buckets_sondeados"]}
                            t0 = time.perf_counter()
                            r = evaluar_de(e, lb, cand)
                            filas.append({"espacio": nombre, "conjunto": cj, "centrado": centrado, "n_bits": b,
                                          "n_tablas": n_tablas, "radio_max": radio, "memoria_Lb": b * n_tablas, **r,
                                          "ms_por_consulta": 1000 * (time.perf_counter() - t0) / len(lb.top),
                                          "segundos_construccion": t_construir, **est})
            mejor = [f for f in filas if f["espacio"] == nombre and f["conjunto"] == "cortas" and f["centrado"] == centrado]
            fb, _ = elegir(mejor, CLAVES_DESEMPATE)
            print(f"  {nombre} {'centrado' if centrado else 'sin centrar'}: mejor según el criterio b={fb['n_bits']} "
                  f"L={fb['n_tablas']} radio={fb['radio_max']} -> recall tol {fb['recall_tolerante']:.3f} "
                  f"costo {fb['costo']:.4f} ({time.perf_counter() - t_inicio:.0f} s)")
        for cj in ("cortas", "documentos"):
            fs = [f for f in filas if f["espacio"] == nombre and f["conjunto"] == cj]
            f, motivo = elegir(fs, CLAVES_DESEMPATE)
            if cj == "cortas":
                elegidos[nombre], motivos[nombre] = f, motivo
            else:
                secundarios[nombre] = (f, motivo)
            print(f"  -> {nombre} [{cj}{' = OFICIAL' if cj == 'cortas' else ', secundario'}]: b = {f['n_bits']}, "
                  f"L = {f['n_tablas']}, radio = {f['radio_max']}, centrado = {f['centrado']} ({motivo}); "
                  f"recall tol {f['recall_tolerante']:.3f} estr {f['recall_estricto']:.3f} costo {f['costo']:.4f}"
                  + (f"; EN EL BORDE: {en_borde(f)}" if en_borde(f) else ""))

    with open(informe / CSV_V2, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    graficar_v2(filas, elegidos)
    print(f"-> informe/{CSV_V2}, informe/validacion_cortas_lsh.png")

    meta = {"semilla": SEMILLA_LSH, "hiperplanos": "numpy.random.default_rng(semilla).normal(0, 1, (L, b, d))",
            "bit": "1 si H·(x - media) >= 0 (media = 0 sin centrado)",
            "multiprobe": "Hamming 1..radio_max (sin pasar de b) mientras haya menos de K = 10 candidatos",
            "protocolo": "Fase 4b: elección con 200 consultas cortas (semilla 20261112); documentos completos secundario",
            "criterio": "menor costo medio con recall tolerante medio >= 0.90; desempate mayor recall, menor L*b, "
                        "menor radio, sin centrado",
            "consultas_cortas": est_cortas, "base": indice_mod.hash_base(), "espacios": {}}
    for nombre, f in elegidos.items():
        lsh = construir(nombre, esp[nombre].x, f["n_bits"], f["n_tablas"], centrado=f["centrado"],
                        radio_max=f["radio_max"])
        archivos = guardar(lsh, indice_mod.INDICE_DIR)
        doc = next(x for x in filas if x["espacio"] == nombre and x["conjunto"] == "documentos"
                   and all(x[k] == f[k] for k in ("n_bits", "n_tablas", "radio_max", "centrado")))
        sec, motsec = secundarios[nombre]
        meta["espacios"][nombre] = {
            "n_bits": f["n_bits"], "n_tablas": f["n_tablas"], "radio_max": f["radio_max"], "centrado": f["centrado"],
            "motivo": motivos[nombre], "en_borde_de_grilla": en_borde(f), "archivos": archivos,
            "cortas": {k: f[k] for k in ("recall_tolerante", "recall_estricto", "costo")},
            "documentos": {k: doc[k] for k in ("recall_tolerante", "recall_estricto", "costo")},
            "eleccion_con_documentos_secundaria": {k: sec[k] for k in ("n_bits", "n_tablas", "radio_max", "centrado",
                                                                       "recall_tolerante", "costo")},
            **{k: f[k] for k in ("bucket_min", "bucket_mediana", "bucket_max", "grupos_identicos",
                                 "docs_en_grupos_identicos", "casi_identicos_mismo_bucket_por_tabla",
                                 "casi_identicos_mismo_bucket_en_alguna_tabla")}}
    indice_mod.actualizar_manifiesto(indice_mod.INDICE_DIR, "lsh", meta)
    print(f"Persistido en indice/: { {n: (m['n_bits'], m['n_tablas'], m['radio_max'], m['centrado']) for n, m in meta['espacios'].items()} } "
          f"({time.perf_counter() - t_inicio:.0f} s en total)")


if __name__ == "__main__":
    import sys
    solo_grafico() if "--solo-grafico" in sys.argv else main()
