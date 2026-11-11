"""Tests de las partes "a mano" de K-Means, LSH y las métricas de validación (Fase 4)."""
import numpy as np
import pytest

import kmeans_indice as K
import lsh_indice as L
from validacion import (
    Espacio, elegir, evaluar, linea_base, muestra_validacion, normalizar_filas, ordenar_top, recall_estricto,
    recall_tolerante,
)


def _datos(n=60, d=5, semilla=0):
    rng = np.random.default_rng(semilla)
    centros = np.eye(d)[:3] * 5
    x = np.vstack([c + rng.normal(0, 0.3, (n // 3, d)) for c in centros])
    return normalizar_filas(x)


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
def test_muestra_fija_y_sin_repetidos():
    a, b = muestra_validacion(1861), muestra_validacion(1861)
    assert np.array_equal(a, b) and a.size == 200 and np.unique(a).size == 200


def test_recall_estricto_y_tolerante_con_empates():
    base_ids, base_p = np.array([1, 2, 3]), np.array([0.9, 0.5, 0.5])
    # el optimizado devuelve otro documento del grupo empatado en 0,5: estricto lo castiga, tolerante no
    opt_ids, opt_p = np.array([1, 2, 7]), np.array([0.9, 0.5, 0.5])
    assert recall_estricto(opt_ids, base_ids) == pytest.approx(2 / 3)
    assert recall_tolerante(opt_p, base_p) == 1.0
    assert recall_tolerante(np.array([0.9, 0.4]), base_p) == pytest.approx(1 / 3)  # faltan y uno peor


def test_ordenar_top_desempata_por_indice():
    t, s = ordenar_top(np.array([5, 2, 9, 1]), np.array([0.5, 0.5, 0.7, 0.5]), 3)
    assert t.tolist() == [9, 1, 2]


def test_evaluar_exhaustivo_da_recall_1_y_costo_1():
    x = _datos()
    e = Espacio("t", x)
    lb = linea_base(e, np.array([0, 25, 50]))
    r = evaluar(e, lb, lambda i: (np.arange(x.shape[0]), {}))
    assert r["recall_tolerante"] == 1.0 and r["recall_estricto"] == 1.0 and r["costo"] == pytest.approx(1.0)


def test_elegir_menor_costo_con_umbral_y_alternativa():
    filas = [{"recall_tolerante": 0.95, "costo": 0.3, "m": 1}, {"recall_tolerante": 0.91, "costo": 0.1, "m": 2},
             {"recall_tolerante": 0.85, "costo": 0.01, "m": 3}]
    assert elegir(filas, "m")[0]["m"] == 2
    assert elegir([filas[2]], "m")[0]["m"] == 3  # nadie llega: el de mayor recall


# ---------------------------------------------------------------------------
# K-Means
# ---------------------------------------------------------------------------
def test_mapa_inverso_y_asignacion_coseno():
    asig = np.array([2, 0, 2, 1, 0])
    indptr, docs = K.mapa_inverso(asig, 4)
    assert indptr.tolist() == [0, 2, 3, 5, 5] and docs.tolist() == [1, 4, 3, 0, 2]  # clúster 3 vacío
    c = K.normalizar(np.array([[1.0, 0], [0, 1.0]]))
    assert K.asignar(np.array([[0.9, 0.1], [0.2, 0.8]]), c).tolist() == [0, 1]


def test_kmeans_consulta_cae_en_su_cluster_y_busca_solo_ahi():
    x = _datos()
    ix, diag = K.construir("t", x, 3)
    assert diag["vacios"] == 0 and sorted(ix.tamanos().tolist()) == [20, 20, 20]
    for i in (0, 25, 59):
        docs, cl = ix.candidatos(x[i], 1)
        assert ix.asignacion[i] == cl[0] and i in docs and docs.size == 20
    docs2, cl2 = ix.candidatos(x[0], 2)
    assert docs2.size == 40 and len(cl2) == 2


def test_silueta_manual_igual_a_sklearn():
    metrics = pytest.importorskip("sklearn.metrics")
    x = _datos()
    asig = K.asignar(x, K.normalizar(K.entrenar_centroides(x, 3)[0]))
    assert K.silueta_coseno(x, asig) == pytest.approx(metrics.silhouette_score(x, asig, metric="cosine"), abs=1e-10)


def test_kmeans_persistencia(tmp_path):
    x = _datos()
    ix, _ = K.construir("t", x, 3)
    K.guardar(ix, tmp_path)
    ix2 = K.cargar(tmp_path, "t")
    assert np.array_equal(ix.centroides, ix2.centroides) and np.array_equal(ix.inverso_docs, ix2.inverso_docs)


# ---------------------------------------------------------------------------
# LSH
# ---------------------------------------------------------------------------
def test_empaquetar_bits_a_mano():
    bits = np.array([[True, False, True], [False, False, False], [True, True, True]])
    assert L.empaquetar(bits).tolist() == [0b101, 0, 0b111]


def test_firmas_buckets_e_identicos_colisionan():
    x = _datos()
    x = np.vstack([x, x[:3]])  # 3 duplicados exactos
    ix = L.construir("t", x, n_bits=6, n_tablas=3)
    assert ix.firmas.shape == (3, 63)
    for l in range(3):  # todo documento está en el bucket de su firma, y una sola vez
        assert sum(len(v) for v in ix.buckets[l].values()) == 63
        assert all(i in ix.buckets[l][int(ix.firmas[l, i])] for i in range(63))
    assert np.array_equal(ix.firmas[:, :3], ix.firmas[:, 60:])
    est = L.estadisticas(ix, L.grupos_identicos(x))
    assert est["grupos_identicos"] == 3 and est["docs_en_grupos_identicos"] == 6 and est["identicos_siempre_colisionan"]


def test_hiperplanos_con_semilla_fija():
    assert np.array_equal(L.generar_hiperplanos(2, 4, 5), L.generar_hiperplanos(2, 4, 5))


def test_multiprobe_hamming_1_y_2():
    ix = L.IndiceLSH("t", np.zeros((1, 4, 2)), np.zeros((1, 0), np.int64), [{0b0000: np.array([0]),
                                                                            0b0001: np.array([1]),
                                                                            0b0011: np.array([2])}])
    ix.firma = lambda q: np.array([0b0000])  # consulta con firma 0000
    c, info = ix.candidatos(np.zeros(2), k=1)
    assert c.tolist() == [0] and info["nivel_multiprobe"] == 0
    c, info = ix.candidatos(np.zeros(2), k=2)
    assert c.tolist() == [0, 1] and info["nivel_multiprobe"] == 1
    c, info = ix.candidatos(np.zeros(2), k=3)
    assert c.tolist() == [0, 1, 2] and info["nivel_multiprobe"] == 2
    c, info = ix.candidatos(np.zeros(2), k=3, permitidos=np.array([False, True, True]), excluir=2)
    assert c.tolist() == [1] and info["nivel_multiprobe"] == 2  # filtro y exclusión cuentan para "< K"
    assert len(list(ix._vecinos(0, 1))) == 4 and len(list(ix._vecinos(0, 2))) == 6


def test_lsh_persistencia(tmp_path):
    x = _datos()
    ix = L.construir("t", x, 8, 2)
    L.guardar(ix, tmp_path)
    ix2 = L.cargar(tmp_path, "t")
    assert np.array_equal(ix.firmas, ix2.firmas)
    for a, b in zip(ix.buckets, ix2.buckets):
        assert a.keys() == b.keys() and all(np.array_equal(a[k], b[k]) for k in a)


# ---------------------------------------------------------------------------
# Fase 4b: centrado, radio de multi-probe y consultas cortas
# ---------------------------------------------------------------------------
def test_centrado_resta_la_media_antes_de_hashear(tmp_path):
    x = _datos() + 0.0
    sin = L.construir("t", x, 8, 2, centrado=False)
    con = L.construir("t", x, 8, 2, centrado=True)
    media = x.sum(axis=0) / x.shape[0]
    assert np.allclose(con.media, media) and sin.media is None
    assert np.array_equal(con.firma(x[0]), sin.firma(x[0] - media))  # mismos hiperplanos (semilla)
    L.guardar(con, tmp_path)
    con2 = L.cargar(tmp_path, "t")
    assert con2.media is not None and np.array_equal(con2.firma(x[5]), con.firma(x[5]))
    L.guardar(sin, tmp_path)  # una elección sin centrado borra la media anterior
    assert L.cargar(tmp_path, "t").media is None


def test_radio_de_multiprobe_hasta_4_sin_pasar_de_b():
    assert len(L.mascaras(16, 3)) == 560 and len(L.mascaras(16, 4)) == 1820
    assert all(bin(m).count("1") == 3 for m in L.mascaras(8, 3))
    ix = L.IndiceLSH("t", np.zeros((1, 4, 2)), np.zeros((1, 0), np.int64), [{0b0111: np.array([3])}], None, 4)
    ix.firma = lambda q: np.array([0b0000])
    c, info = ix.candidatos(np.zeros(2), k=1, radio=2)
    assert c.size == 0 and info["nivel_multiprobe"] == 2
    c, info = ix.candidatos(np.zeros(2), k=1)  # radio del índice = 4: llega a Hamming 3
    assert c.tolist() == [3] and info["nivel_multiprobe"] == 3
    ix2 = L.IndiceLSH("t", np.zeros((1, 2, 2)), np.zeros((1, 0), np.int64), [{0b11: np.array([7])}], None, 4)
    ix2.firma = lambda q: np.array([0b00])
    c, info = ix2.candidatos(np.zeros(2), k=1)  # b = 2: el radio se corta en 2
    assert c.tolist() == [7] and info["nivel_multiprobe"] == 2


def test_consultas_cortas_reproducibles_y_con_informacion():
    from validacion import consultas_cortas
    headers = [{"ESO DPR TYPE": "FLAT,SKY", "OBJECT": "BIAS", "EXPTIME": 1.0},
               {"ESO DPR TYPE": "BIAS", "OBJECT": "BIAS", "ESO INS FILT1 NAME": "B"},
               {"ESO DPR TYPE": "DARK", "OBJECT": "DARK"}]
    from tokenizer import tokenizar
    df = {}
    for h in headers:
        for t in {t for k, v in h.items() if isinstance(v, str) for t in tokenizar(v, llave=k)}:
            df[t] = df.get(t, 0) + 1
    a, est = consultas_cortas(headers, df, 3, n=20, semilla=7)
    b, _ = consultas_cortas(headers, df, 3, n=20, semilla=7)
    assert [c["tokens"] for c in a] == [c["tokens"] for c in b]  # semilla fija
    assert all(1 <= len(c["tokens"]) <= 4 for c in a)
    assert all(any(df[t] < 3 for t in c["tokens"]) for c in a)  # ninguna con todos df = N
    assert est["reemplazadas"] > 0 and est["motivos_reemplazo"]["todos_df_N"] == est["reemplazadas"]
    assert all(c["llave"] in ("ESO DPR TYPE", "OBJECT", "ESO INS FILT1 NAME") for c in a)  # solo pares de texto
