"""Tests del benchmark (Fase 6): estadísticos, plan y reanudación, condiciones y pausa, integridad.

La pasada de tiempo se prueba con un buscador falso (rápido) y un monitor falso: no requieren
MongoDB ni PowerShell.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pytest

import benchmark as B


def test_estadisticas_formato_tabla_1():
    v = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    e = B.estadisticas(v)
    assert list(B.ESTADISTICOS) == ["MIN", "Q1", "MEDIAN", "Q3", "MAX", "IQR", "MEAN", "STD"]
    assert (e["MIN"], e["Q1"], e["MEDIAN"], e["Q3"], e["MAX"]) == (1, 2, 3, 4, 100)
    assert e["IQR"] == 2 and e["MEAN"] == 22 and e["STD"] == pytest.approx(np.std(v, ddof=1)) and e["n"] == 5


def test_plan_reproducible_reanuda_y_rechaza_otros_parametros(tmp_path):
    p1 = B.plan_de(tmp_path, "tiempo", 3000, B.PARES, B.SEMILLA_BENCHMARK)
    assert p1["rondas"] == 3 and all(sorted(o) == list(range(30)) for o in p1["ordenes"])
    assert len({tuple(o) for o in p1["ordenes"]}) == 3  # una permutación distinta por ronda
    p2 = B.plan_de(tmp_path, "tiempo", 3000, B.PARES, B.SEMILLA_BENCHMARK)
    assert p2["ordenes"] == p1["ordenes"]
    with pytest.raises(SystemExit):
        B.plan_de(tmp_path, "tiempo", 4000, B.PARES, B.SEMILLA_BENCHMARK)
    with pytest.raises(ValueError):
        B.plan_de(tmp_path / "otra", "tiempo", 1500, B.PARES, B.SEMILLA_BENCHMARK)


def test_guardar_atomico_no_deja_temporales(tmp_path):
    B.guardar_atomico(tmp_path / "ronda_00000.npy", lambda fh: np.save(fh, np.arange(3)))
    assert np.load(tmp_path / "ronda_00000.npy").tolist() == [0, 1, 2]
    assert [p.name for p in tmp_path.iterdir()] == ["ronda_00000.npy"]


# ---------------------------------------------------------------------------
# Condiciones
# ---------------------------------------------------------------------------
def _monitor_con(tmp_path, bateria="2", modo=B.MODO_MAXIMO, edad_s=0):
    t = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - edad_s, timezone.utc)
    m = B.Monitor(tmp_path)
    m.csv.write_text(f"{t.strftime('%Y-%m-%dT%H:%M:%S')}Z|1585|200|5|{bateria}|90|{modo}|12000\n", encoding="ascii")
    return m


@pytest.fixture
def sin_hdfs(monkeypatch):
    monkeypatch.setattr(B, "puertos_abiertos", lambda puertos=B.PUERTOS_HDFS: [])


def test_condiciones_validas_y_frecuencia_efectiva(tmp_path, sin_hdfs):
    c = B.condiciones(_monitor_con(tmp_path))
    assert c["validas"] and c["monitor"]["mhz_efectivos"] == 3170


@pytest.mark.parametrize("kw, motivo", [({"bateria": "1"}, "batería"), ({"modo": ""}, "Máximo rendimiento"),
                                        ({"edad_s": 300}, "monitor")])
def test_condiciones_invalidas_pausan(tmp_path, sin_hdfs, kw, motivo):
    m = _monitor_con(tmp_path, **kw)
    with pytest.raises(B.Pausa, match=motivo):
        B.checkpoint(tmp_path, m, "ronda")
    ev = json.loads((tmp_path / "condiciones.jsonl").read_text().splitlines()[-1])
    assert ev["validas"] is False and any(motivo in x for x in ev["motivos"])


def test_hdfs_encendido_pausa(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "puertos_abiertos", lambda puertos=B.PUERTOS_HDFS: [9870])
    with pytest.raises(B.Pausa, match="HDFS"):
        B.checkpoint(tmp_path, _monitor_con(tmp_path), "ronda")


# ---------------------------------------------------------------------------
# Pasada de tiempo con buscador falso: datos, reanudación e integridad
# ---------------------------------------------------------------------------
class _Res:
    def __init__(self, rutas):
        self.resultados = [{"hdfs_path": r} for r in rutas]


class _BuscadorFalso:
    llamadas = 0
    cambiar_en = None

    def __init__(self, *a, **k):
        self.blas = []

    def buscar(self, modelo, optim, top, **kw):
        _BuscadorFalso.llamadas += 1
        if _BuscadorFalso.cambiar_en is not None and _BuscadorFalso.llamadas > _BuscadorFalso.cambiar_en:
            return _Res(["otra"])
        return _Res([f"/{modelo}/{optim}/{kw.get('texto', 'num')}"])

    def cerrar(self):
        pass


class _MonitorFalso(B.Monitor):
    def ultima(self):
        return {"edad_s": 0, "bateria_estado": "2", "modo_ac": B.MODO_MAXIMO, "mhz_efectivos": 3000}


@pytest.fixture
def falso(monkeypatch, sin_hdfs):
    import buscador
    monkeypatch.setattr(buscador, "Buscador", _BuscadorFalso)
    monkeypatch.setattr("entorno.resumen_equipo", lambda: {"falso": True})
    _BuscadorFalso.llamadas, _BuscadorFalso.cambiar_en = 0, None


def test_pasada_tiempo_guarda_rondas_y_reanuda(tmp_path, falso):
    mon = _MonitorFalso(tmp_path)
    B.pasada_tiempo(tmp_path, 2000, mon)
    r0, r1 = tmp_path / "tiempo" / "ronda_00000.npz", tmp_path / "tiempo" / "ronda_00001.npz"
    z = np.load(r0)
    datos = z["tiempo_ns"]
    assert datos.shape == (30, 1000) and (datos > 0).all()
    assert (z["bloque_raw_ns"] >= datos.sum(axis=1)).all() and (z["bloque_monotonic_ns"] > 0).all()
    assert json.loads((tmp_path / "tiempo" / "plan.json").read_text())["reloj"] == "CLOCK_MONOTONIC_RAW"
    # calentamiento (30 × 1000) + 2 rondas (30 × 1000 c/u)
    assert _BuscadorFalso.llamadas == 30 * B.CALENTAMIENTO + 2 * 30 * B.BLOQUE
    mtime0 = r0.stat().st_mtime_ns
    r1.unlink()
    _BuscadorFalso.llamadas = 0
    B.pasada_tiempo(tmp_path, 2000, mon)  # reanuda: solo la ronda 1
    assert r1.exists() and r0.stat().st_mtime_ns == mtime0
    assert _BuscadorFalso.llamadas == 30 * B.CALENTAMIENTO + 30 * B.BLOQUE
    ev = [json.loads(l)["evento"] for l in (tmp_path / "tiempo" / "condiciones.jsonl").read_text().splitlines()]
    assert ev.count("inicio") == 2 and ev.count("ronda") == 3 and ev.count("sesion") == 2  # 2 + 1 reanudada


def test_pasada_tiempo_detecta_resultado_cambiado(tmp_path, falso):
    _BuscadorFalso.cambiar_en = 30 * B.CALENTAMIENTO + 500
    with pytest.raises(RuntimeError, match="cambió"):
        B.pasada_tiempo(tmp_path, 1000, _MonitorFalso(tmp_path))
    assert not list((tmp_path / "tiempo").glob("ronda_*.npz"))  # la ronda incompleta no se guarda


def test_resumen_tablas_desde_datos_crudos(tmp_path, falso):
    B.pasada_tiempo(tmp_path, 1000, _MonitorFalso(tmp_path))
    B.resumen(tmp_path, tmp_path / "res")
    filas = (tmp_path / "res" / "benchmark_tiempo.csv").read_text().splitlines()
    assert len(filas) == 1 + 6 * 6  # 6 agregadas + 30 por consulta
    assert "Tabla 1 — Tiempo" in (tmp_path / "res" / "benchmark_resumen.md").read_text()
