"""Índice K-Means para restringir la búsqueda por coseno a un clúster (Fase 4A).

- Centroides: **solo** ``sklearn.cluster.KMeans`` (``random_state = 20261111``,
  ``n_init = 10``, algoritmo de Lloyd por defecto), por separado en el espacio TF-IDF (filas
  con norma 1) y en el LSI (k = 14, filas normalizadas con L2; ver ``espacios.py``).
- A mano:
  * asignación documento → clúster por **coseno máximo** con los centroides (la misma regla que
    para las consultas: un documento usado como consulta cae en su propio clúster);
  * mapa inverso clúster → documentos (``indptr`` + ``docs``, como una CSR);
  * consulta → los ``n_probe`` centroides más cercanos por coseno (1 por defecto, lo que pide
    el enunciado) → coseno exacto **solo** sobre los documentos de esos clústeres;
  * inercia y silueta (distancia coseno) como diagnóstico.

Uso (barrido de validación + persistencia del elegido):
    python src/kmeans_indice.py
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass

import numpy as np

SEMILLA_KMEANS = 20261111
N_INIT = 10
CLUSTERES = (4, 8, 16, 32, 64)            # grilla de la primera validación
CLUSTERES_V2 = (4, 8, 16, 32, 64, 128)    # grilla de la Fase 4b
N_PROBE_POR_DEFECTO = 1


@dataclass
class IndiceKMeans:
    espacio: str
    centroides: np.ndarray      # c × d, filas con norma 1 (el coseno no depende de la escala)
    asignacion: np.ndarray      # N, clúster de cada documento
    inverso_indptr: np.ndarray  # c + 1
    inverso_docs: np.ndarray    # N, documentos ordenados por clúster

    @property
    def n_clusteres(self) -> int:
        return self.centroides.shape[0]

    def miembros(self, c: int) -> np.ndarray:
        return self.inverso_docs[self.inverso_indptr[c]:self.inverso_indptr[c + 1]]

    def tamanos(self) -> np.ndarray:
        return np.diff(self.inverso_indptr)

    def clusteres_cercanos(self, q: np.ndarray, n_probe: int = N_PROBE_POR_DEFECTO) -> np.ndarray:
        """Los ``n_probe`` clústeres de mayor coseno con ``q`` (empate: índice menor)."""
        cos = self.centroides @ q / (np.sqrt(np.dot(q, q)) or 1.0)
        return np.lexsort((np.arange(cos.size), -cos))[:n_probe]

    def candidatos(self, q: np.ndarray, n_probe: int = N_PROBE_POR_DEFECTO) -> tuple[np.ndarray, np.ndarray]:
        """``(documentos de los clústeres sondeados, clústeres)``."""
        cl = self.clusteres_cercanos(q, n_probe)
        docs = np.concatenate([self.miembros(c) for c in cl]) if cl.size else np.empty(0, np.int64)
        return np.sort(docs), cl


# ---------------------------------------------------------------------------
# Construcción (a mano salvo los centroides)
# ---------------------------------------------------------------------------
def entrenar_centroides(x: np.ndarray, c: int, semilla: int = SEMILLA_KMEANS, n_init: int = N_INIT):
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=c, random_state=semilla, n_init=n_init).fit(x)
    return km.cluster_centers_, km


def normalizar(m: np.ndarray) -> np.ndarray:
    n = np.sqrt(np.einsum("ij,ij->i", m, m))
    n[n == 0] = 1.0
    return m / n[:, None]


def asignar(x: np.ndarray, centroides_unit: np.ndarray) -> np.ndarray:
    """Clúster de coseno máximo para cada fila de ``x`` (filas con norma 1); empate → índice menor."""
    return np.argmax(x @ centroides_unit.T, axis=1)  # argmax devuelve el primer máximo


def mapa_inverso(asignacion: np.ndarray, c: int) -> tuple[np.ndarray, np.ndarray]:
    """Ordenamiento por conteo: ``indptr`` (c+1) y documentos agrupados por clúster (ascendentes)."""
    conteo = np.zeros(c, dtype=np.int64)
    for a in asignacion:
        conteo[a] += 1
    indptr = np.zeros(c + 1, dtype=np.int64)
    indptr[1:] = np.cumsum(conteo)
    docs = np.empty(asignacion.size, dtype=np.int64)
    siguiente = indptr[:-1].copy()
    for i, a in enumerate(asignacion):
        docs[siguiente[a]] = i
        siguiente[a] += 1
    return indptr, docs


def inercia(x: np.ndarray, centroides: np.ndarray, asignacion: np.ndarray) -> float:
    d = x - centroides[asignacion]
    return float(np.einsum("ij,ij->", d, d))


def silueta_coseno(x: np.ndarray, asignacion: np.ndarray) -> float:
    """Silueta media con distancia 1 − coseno (filas con norma 1). Clúster de 1 elemento → s = 0."""
    dist = 1.0 - x @ x.T
    etiquetas = np.unique(asignacion)
    if etiquetas.size < 2:
        return float("nan")
    sumas = np.stack([dist[:, asignacion == c].sum(axis=1) for c in etiquetas], axis=1)  # N × c
    tam = np.array([(asignacion == c).sum() for c in etiquetas])
    propio = np.searchsorted(etiquetas, asignacion)
    filas = np.arange(x.shape[0])
    n_propio = tam[propio]
    a = np.where(n_propio > 1, sumas[filas, propio] / np.maximum(n_propio - 1, 1), 0.0)
    medias = sumas / tam[None, :]
    medias[filas, propio] = np.inf
    b = medias.min(axis=1)
    s = np.where(n_propio > 1, (b - a) / np.maximum(np.maximum(a, b), 1e-15), 0.0)
    return float(s.mean())


def construir(espacio: str, x: np.ndarray, c: int, semilla: int = SEMILLA_KMEANS,
              n_init: int = N_INIT) -> tuple[IndiceKMeans, dict]:
    centroides, km = entrenar_centroides(x, c, semilla, n_init)
    cu = normalizar(centroides)
    asig = asignar(x, cu)
    indptr, docs = mapa_inverso(asig, c)
    tam = np.diff(indptr)
    diag = {
        "inercia_sklearn": float(km.inertia_),
        "inercia_asignacion_coseno": inercia(x, centroides, asig),
        "silueta_coseno": silueta_coseno(x, asig),
        "acuerdo_con_labels_sklearn": float(np.mean(asig == km.labels_)),
        "tam_min": int(tam.min()), "tam_mediana": float(np.median(tam)), "tam_max": int(tam.max()),
        "vacios": int((tam == 0).sum()), "unitarios": int((tam == 1).sum()),
        "fraccion_mayor": float(tam.max() / x.shape[0]),
        "iteraciones_sklearn": int(km.n_iter_),
    }
    return IndiceKMeans(espacio, cu, asig, indptr, docs), diag


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def guardar(ix: IndiceKMeans, directorio) -> list[str]:
    pref = f"kmeans_{ix.espacio}"
    np.save(directorio / f"{pref}_centroides.npy", ix.centroides)
    np.save(directorio / f"{pref}_asignacion.npy", ix.asignacion)
    np.save(directorio / f"{pref}_inverso_indptr.npy", ix.inverso_indptr)
    np.save(directorio / f"{pref}_inverso_docs.npy", ix.inverso_docs)
    return [f"{pref}_{s}.npy" for s in ("centroides", "asignacion", "inverso_indptr", "inverso_docs")]


def cargar(directorio, espacio: str) -> IndiceKMeans:
    pref = f"kmeans_{espacio}"
    return IndiceKMeans(espacio, np.load(directorio / f"{pref}_centroides.npy"),
                        np.load(directorio / f"{pref}_asignacion.npy"),
                        np.load(directorio / f"{pref}_inverso_indptr.npy"),
                        np.load(directorio / f"{pref}_inverso_docs.npy"))


# ---------------------------------------------------------------------------
# Barrido de validación (Fase 4b): consultas cortas = oficial; documentos = secundario
# ---------------------------------------------------------------------------
CSV_V2 = "validacion_v2_kmeans.csv"


def panel(nombre: str, filas_esp: list[dict], elegida: dict) -> dict:
    series = []
    for n_probe in (1, 2):
        fs = sorted((x for x in filas_esp if int(x["n_probe"]) == n_probe), key=lambda x: int(x["n_clusteres"]))
        serie = {"nombre": f"n_probe = {n_probe}" + (" (enunciado)" if n_probe == 1 else " (referencia)"),
                 "x": [float(x["costo"]) for x in fs], "y": [float(x["recall_tolerante"]) for x in fs]}
        if n_probe == 1:  # etiquetado selectivo: solo la serie que decide
            serie["etiquetas"] = [f"c={x['n_clusteres']}" for x in fs]
        series.append(serie)
    return {"titulo": f"Espacio {nombre.upper()}", "series": series,
            "elegido": {"x": float(elegida["costo"]), "y": float(elegida["recall_tolerante"]),
                        "texto": f"elegido: c = {elegida['n_clusteres']}"}}


def graficar_v2(filas: list[dict], elegidos: dict) -> None:
    from config import ENTREGA2_DIR
    from graficos import curvas_costo_recall
    from validacion import UMBRAL_RECALL
    paneles = [panel(n, [f for f in filas if f["espacio"] == n and f["conjunto"] == "cortas"], elegidos[n])
               for n in ("tfidf", "lsi")]
    curvas_costo_recall(paneles, ENTREGA2_DIR / "informe" / "validacion_cortas_kmeans.png", UMBRAL_RECALL,
                        "K-Means: costo vs. recall relativo — 200 consultas cortas")


def solo_grafico() -> None:
    import json

    import indice as indice_mod
    from config import ENTREGA2_DIR
    filas = list(csv.DictReader(open(ENTREGA2_DIR / "informe" / CSV_V2, encoding="utf-8")))
    man = json.loads((indice_mod.INDICE_DIR / "manifiesto.json").read_text())["kmeans"]["espacios"]
    elegidos = {n: next(f for f in filas if f["espacio"] == n and f["conjunto"] == "cortas" and f["n_probe"] == "1"
                        and int(f["n_clusteres"]) == man[n]["n_clusteres"]) for n in ("tfidf", "lsi")}
    graficar_v2(filas, elegidos)


def main() -> None:
    import conjuntos
    import indice as indice_mod
    from config import ENTREGA2_DIR
    from espacios import ESPACIOS, espacios_desde_indice
    from validacion import elegir, evaluar_de, linea_base_de

    informe = ENTREGA2_DIR / "informe"
    ix = indice_mod.cargar()
    esp = espacios_desde_indice(ix)
    conj, _, est_cortas = conjuntos.preparar(ix, esp)
    print(f"Consultas cortas: {est_cortas}")
    filas, elegidos, motivos, secundarios, construidos = [], {}, {}, {}, {}
    for nombre in ESPACIOS:
        e = esp[nombre]
        lbs = {c: linea_base_de(e, conj[nombre][c]) for c in ("cortas", "documentos")}
        for c in CLUSTERES_V2:
            t0 = time.perf_counter()
            km, diag = construir(nombre, e.x, c)
            construidos[(nombre, c)] = km
            t_construir = time.perf_counter() - t0
            for n_probe in (1, 2):
                for cj, lb in lbs.items():
                    def cand(j, q, excl, km=km, n_probe=n_probe):
                        docs, _ = km.candidatos(q, n_probe)
                        return docs, {}
                    t0 = time.perf_counter()
                    r = evaluar_de(e, lb, cand)
                    filas.append({"espacio": nombre, "conjunto": cj, "n_clusteres": c, "n_probe": n_probe, **r,
                                  "ms_por_consulta": 1000 * (time.perf_counter() - t0) / len(lb.top),
                                  "segundos_construccion": t_construir, **diag})
                    if n_probe == 1:
                        print(f"  {nombre:<5} c={c:<3} [{cj:<10}] recall tol {r['recall_tolerante']:.3f} estr "
                              f"{r['recall_estricto']:.3f} costo {r['costo']:.4f} <10 cand {r['consultas_con_menos_de_k']} "
                              f"| tamaños {diag['tam_min']}/{diag['tam_mediana']:.0f}/{diag['tam_max']} "
                              f"unitarios {diag['unitarios']} | silueta {diag['silueta_coseno']:.3f}")
        for cj in ("cortas", "documentos"):
            fs = [f for f in filas if f["espacio"] == nombre and f["conjunto"] == cj and f["n_probe"] == N_PROBE_POR_DEFECTO]
            f, motivo = elegir(fs, "n_clusteres")
            if cj == "cortas":
                elegidos[nombre], motivos[nombre] = f, motivo
            else:
                secundarios[nombre] = (f, motivo)
            borde = f["n_clusteres"] in (min(CLUSTERES_V2), max(CLUSTERES_V2))
            print(f"  -> {nombre} [{cj}{' = OFICIAL' if cj == 'cortas' else ', secundario'}]: c = {f['n_clusteres']} "
                  f"({motivo}); recall tol {f['recall_tolerante']:.3f} costo {f['costo']:.4f}"
                  + ("; EN EL BORDE DE LA GRILLA" if borde else ""))

    with open(informe / CSV_V2, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    graficar_v2(filas, elegidos)
    print(f"-> informe/{CSV_V2}, informe/validacion_cortas_kmeans.png")

    meta = {"semilla": SEMILLA_KMEANS, "n_init": N_INIT, "algoritmo": "sklearn.cluster.KMeans (Lloyd) solo para centroides",
            "asignacion": "coseno maximo (a mano)", "n_probe_por_defecto": N_PROBE_POR_DEFECTO,
            "protocolo": "Fase 4b: elección con 200 consultas cortas (semilla 20261112); documentos completos secundario",
            "criterio": "menor costo medio con recall tolerante medio >= 0.90 (n_probe = 1); desempate mayor recall, menor c",
            "consultas_cortas": est_cortas, "base": indice_mod.hash_base(), "espacios": {}}
    for nombre, f in elegidos.items():
        km = construidos[(nombre, f["n_clusteres"])]
        archivos = guardar(km, indice_mod.INDICE_DIR)
        doc = next(x for x in filas if x["espacio"] == nombre and x["conjunto"] == "documentos"
                   and x["n_clusteres"] == f["n_clusteres"] and x["n_probe"] == N_PROBE_POR_DEFECTO)
        sec, _ = secundarios[nombre]
        meta["espacios"][nombre] = {
            "n_clusteres": f["n_clusteres"], "motivo": motivos[nombre],
            "en_borde_de_grilla": f["n_clusteres"] in (min(CLUSTERES_V2), max(CLUSTERES_V2)), "archivos": archivos,
            "cortas": {k: f[k] for k in ("recall_tolerante", "recall_estricto", "costo")},
            "documentos": {k: doc[k] for k in ("recall_tolerante", "recall_estricto", "costo")},
            "eleccion_con_documentos_secundaria": {"n_clusteres": sec["n_clusteres"],
                                                   "recall_tolerante": sec["recall_tolerante"], "costo": sec["costo"]},
            **{k: f[k] for k in ("tam_min", "tam_mediana", "tam_max", "vacios", "unitarios", "silueta_coseno",
                                 "inercia_sklearn")}}
    indice_mod.actualizar_manifiesto(indice_mod.INDICE_DIR, "kmeans", meta)
    print(f"Persistido en indice/: { {n: m['n_clusteres'] for n, m in meta['espacios'].items()} }")


if __name__ == "__main__":
    import sys
    solo_grafico() if "--solo-grafico" in sys.argv else main()
