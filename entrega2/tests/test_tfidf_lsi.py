"""Validación de TF-IDF, LSI y coseno sobre un corpus de juguete.

- TF-IDF: comparado con un cálculo hecho a mano en el test y, **solo aquí**, con
  ``sklearn.feature_extraction.text.TfidfVectorizer`` configurado de forma equivalente.
- LSI: con k = rango completo, ``U Σ Vᵀ`` reconstruye la matriz; los documentos proyectados con
  ``Σ_k⁻¹ U_kᵀ d`` coinciden con ``V_k``.
- Coseno: fórmula, norma 0 y top-K determinista.
"""
import math

import numpy as np
import pytest

import lsi
import tfidf
from similitud import buscar, coseno, cosenos, normas_filas, top_k

DOCS = [
    ["flat", "sky", "flat"],
    ["bias", "dark"],
    ["flat", "lamp"],
    ["sky", "zenith", "sky", "sky"],
]
N = len(DOCS)


def test_vocabulario_df_idf_a_mano():
    m = tfidf.ajustar(DOCS)
    assert m.vocabulario == ["bias", "dark", "flat", "lamp", "sky", "zenith"]
    assert m.df.tolist() == [1, 1, 2, 1, 2, 1]
    # suavizado: ln((1+N)/(1+df)) + 1, N = 4
    assert m.idf == pytest.approx([math.log(5 / 2) + 1, math.log(5 / 2) + 1, math.log(5 / 3) + 1,
                                   math.log(5 / 2) + 1, math.log(5 / 3) + 1, math.log(5 / 2) + 1])
    clasico = tfidf.calcular_idf(m.df, N, "clasico")
    assert clasico == pytest.approx([math.log(4), math.log(4), math.log(2), math.log(4), math.log(2), math.log(4)])


def test_matriz_a_mano():
    m = tfidf.ajustar(DOCS)
    i_flat, i_sky = math.log(5 / 3) + 1, math.log(5 / 3) + 1
    # documento 0: tf(flat) = 2, tf(sky) = 1
    w = np.array([2 * i_flat, 1 * i_sky])
    w = w / np.linalg.norm(w)
    x = m.matriz.toarray()
    assert x.shape == (4, 6)
    assert x[0] == pytest.approx([0, 0, w[0], 0, w[1], 0])
    assert normas_filas(m.matriz) == pytest.approx(np.ones(4))


def test_igual_a_sklearn_configurado_equivalente():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    v = sk.TfidfVectorizer(analyzer=lambda d: d, lowercase=False, use_idf=True, smooth_idf=True,
                           sublinear_tf=False, norm="l2")
    x_sk = v.fit_transform(DOCS)
    m = tfidf.ajustar(DOCS)
    assert list(v.get_feature_names_out()) == m.vocabulario
    assert v.idf_ == pytest.approx(m.idf)
    assert np.abs(x_sk.toarray() - m.matriz.toarray()).max() < 1e-12


def test_consulta_oov_y_norma_cero():
    m = tfidf.ajustar(DOCS)
    q, oov = m.vectorizar_consulta(["flat", "filt", "ins"])
    assert oov == ["filt", "ins"] and np.linalg.norm(q) == pytest.approx(1.0)
    assert q[m.indice["flat"]] == pytest.approx(1.0)
    q0, oov0 = m.vectorizar_consulta(["filt"])
    assert q0 is None and oov0 == ["filt"]
    # IDF clásico: un término en todos los documentos pesa 0 -> consulta de norma 0
    m2 = tfidf.ajustar([["a", "b"], ["a"]], variante="clasico")
    assert m2.vectorizar_consulta(["a"])[0] is None


def test_lsi_rango_completo_reconstruye_y_docs_igual_a_V_k():
    m = tfidf.ajustar(DOCS)
    a = m.matriz.toarray().T
    u, s, vt = lsi.svd(a)
    k = s.size
    u_k, s_k, v_k = lsi.truncar(u, s, vt, k)
    assert np.abs(lsi.reconstruir(u_k, s_k, v_k) - a).max() < 1e-12
    docs_k = lsi.proyectar(u_k, s_k, a.T)
    assert np.abs(docs_k - v_k).max() < 1e-12
    modelo, chequeo = lsi.ajustar(m.matriz, k=k)
    assert chequeo["max_abs_docs_k_menos_V_k"] < 1e-12 and chequeo["rango_numerico"] == 4


def test_varianza_y_eleccion_de_k():
    s = np.array([3.0, 2.0, 1.0, 0.0])
    acum = lsi.varianza_explicada_acumulada(s)
    assert acum == pytest.approx([9 / 14, 13 / 14, 1.0, 1.0])
    assert lsi.elegir_k(s, 0.90) == 2 and lsi.elegir_k(s, 13 / 14) == 2 and lsi.elegir_k(s, 0.5) == 1
    # sin_primera: sobre σ2.. = [2, 1, 0] -> [4/5, 1, 1]; k incluye la primera componente
    assert lsi.varianza_sin_primera_acumulada(s) == pytest.approx([0.8, 1.0, 1.0])
    assert lsi.elegir_k(s, 0.80, "sin_primera") == 2 and lsi.elegir_k(s, 0.90, "sin_primera") == 3


def test_consulta_proyectada_con_la_misma_transformacion():
    m = tfidf.ajustar(DOCS)
    modelo, _ = lsi.ajustar(m.matriz, k=2)
    q, _ = m.vectorizar_consulta(["sky"])
    assert modelo.proyectar_consulta(q) == pytest.approx((q @ modelo.u_k) / modelo.s_k)
    # el documento 3 (solo sky/zenith) proyectado como consulta coincide con su fila de docs_k
    d3 = m.matriz.toarray()[3]
    assert modelo.proyectar_consulta(d3) == pytest.approx(modelo.docs_k[3])


def test_coseno_y_top_k():
    assert coseno(np.array([1.0, 0.0]), np.array([1.0, 1.0])) == pytest.approx(1 / math.sqrt(2))
    assert coseno(np.zeros(2), np.array([1.0, 1.0])) == 0.0
    m = np.array([[1.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    p = cosenos(m, np.array([1.0, 0.0]))
    assert p.tolist() == [1.0, 0.0, 1.0, 0.0]  # fila de norma 0 -> 0
    with pytest.warns(UserWarning):
        assert cosenos(m, np.zeros(2)) is None
    ids = ["d0", "d1", "d2", "d3"]
    assert top_k(p, ids, 2) == [("d0", 1.0), ("d2", 1.0)]  # empate -> _id ascendente
    assert top_k(p, ids, 2, candidatos=[3, 2]) == [("d2", 1.0), ("d3", 0.0)]
    assert buscar(m, None, ids, 2) == []
