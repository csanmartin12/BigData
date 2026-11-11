"""Benchmark de la Fase 6: tiempo de respuesta y RAM por consulta (METODOLOGIA.md, Fase 6).

6 configuraciones ({tfidf, lsi} × {ninguna, kmeans, lsh}) × consultas A–E, cada consulta
resuelta como la CLI: ``Buscador.buscar(**consultas.ARGUMENTOS_CLI[c])``.

Pasadas (separadas):

- ``tiempo``: un proceso con todos los índices cargados una vez. Cronómetro por consulta con
  ``CLOCK_MONOTONIC_RAW`` (en este WSL, ``perf_counter_ns`` = CLOCK_MONOTONIC está acelerado
  3–7 % por systemd-timesyncd; METODOLOGIA.md, Fase 6), calentamiento de 1.000 por par sin registrar, gc deshabilitado dentro de cada
  bloque de 1.000 y rondas con los 30 pares en orden aleatorio (semilla fija).
- ``ram``: un proceso nuevo por configuración, que carga solo sus índices
  (``Buscador(solo=...)``). Mide el RSS base y, por consulta, el pico de tracemalloc y el RSS
  posterior.

Datos crudos por ronda en ``salidas/benchmark/<corrida>/`` (escritura atómica). Si se corta,
el mismo comando reanuda desde la última ronda completa. Las condiciones (corriente, modo de
energía, HDFS detenido, memoria, frecuencia de la CPU) se revisan antes de empezar y en cada
checkpoint. Si dejan de ser válidas, se guarda lo medido y se termina con código 3 (pausa).

Uso:
    python src/benchmark.py todo --corrida corta --reps 2000      # tiempo + RAM + resumen
    python src/benchmark.py tiempo --corrida completa --reps 100000
    python src/benchmark.py ram --corrida completa --reps 100000
    python src/benchmark.py resumen --corrida completa
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ENTREGA2_DIR, SALIDAS_DIR  # noqa: E402
from consultas import ARGUMENTOS_CLI  # noqa: E402

SEMILLA_BENCHMARK = 20261113
BLOQUE = 1000
CALENTAMIENTO = 1000
TOP = 10
MODELOS = ("tfidf", "lsi")
OPTIMIZACIONES = ("ninguna", "kmeans", "lsh")
CONFIGS = [(m, o) for m in MODELOS for o in OPTIMIZACIONES]
CONSULTAS_IDS = tuple("ABCDE")
PARES = [(m, o, c) for (m, o) in CONFIGS for c in CONSULTAS_IDS]
NOMBRE = {("tfidf", "ninguna"): "TF-IDF", ("tfidf", "kmeans"): "TF-IDF + K-Means", ("tfidf", "lsh"): "TF-IDF + LSH",
          ("lsi", "ninguna"): "LSI", ("lsi", "kmeans"): "LSI + K-Means", ("lsi", "lsh"): "LSI + LSH"}

PUERTOS_HDFS = (9870, 9864, 9866, 9867, 8020)
MODO_MAXIMO = "ded574b5-45a0-4f42-8737-46345c09c238"
MEM_MINIMA_KIB = 2 * 2**20
EDAD_MAX_MONITOR_S = 90
CODIGO_PAUSA = 3
BENCH_DIR = SALIDAS_DIR / "benchmark"


# Reloj del cronómetro. CLOCK_MONOTONIC (perf_counter_ns) lo ajusta systemd-timesyncd: en este
# WSL corre 3–7 % más rápido que el reloj de Windows (tick 10833 en adjtimex). MONOTONIC_RAW es
# el contador del hardware sin ajustes y coincide con Windows (+0,02 % en 40 s).
RELOJ = "CLOCK_MONOTONIC_RAW"
_RAW = time.CLOCK_MONOTONIC_RAW


def raw_ns() -> int:
    return time.clock_gettime_ns(_RAW)


def raw_s() -> float:
    return time.clock_gettime_ns(_RAW) / 1e9


def ajuste_reloj() -> dict:
    """``tick`` y ``freq`` de adjtimex (cuánto está corrigiendo el kernel a CLOCK_MONOTONIC)."""
    import ctypes
    import ctypes.util

    class Timex(ctypes.Structure):
        _fields_ = [("modes", ctypes.c_uint), ("offset", ctypes.c_long), ("freq", ctypes.c_long),
                    ("maxerror", ctypes.c_long), ("esterror", ctypes.c_long), ("status", ctypes.c_int),
                    ("constant", ctypes.c_long), ("precision", ctypes.c_long), ("tolerance", ctypes.c_long),
                    ("time_sec", ctypes.c_long), ("time_usec", ctypes.c_long), ("tick", ctypes.c_long),
                    ("pad", ctypes.c_long * 30)]
    try:
        t = Timex()
        ctypes.CDLL(ctypes.util.find_library("c")).adjtimex(ctypes.byref(t))
        return {"tick": t.tick, "freq_ppm": round(t.freq / 65536, 1),
                "monotonic_acelerado_pct": round((t.tick / 10000 * (1 + t.freq / 65536 / 1e6) - 1) * 100, 2)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


class Pausa(Exception):
    """Las condiciones de medición dejaron de ser válidas."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def guardar_atomico(ruta: Path, escribir) -> None:
    """``escribir(archivo_tmp)`` y luego ``os.replace``: una ronda queda completa o no queda."""
    tmp = ruta.with_name(ruta.name + ".tmp")
    with open(tmp, "wb") as fh:
        escribir(fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ruta)


def estado_proceso() -> dict:
    """VmRSS y VmHWM del proceso, en KiB."""
    out = {}
    with open("/proc/self/status", "rb") as f:
        for linea in f:
            if linea.startswith((b"VmRSS", b"VmHWM")):
                k, v = linea.split(b":")
                out[k.decode()] = int(v.split()[0])
    return out


def vmrss_kib() -> int:
    with open("/proc/self/status", "rb") as f:
        datos = f.read()
    i = datos.index(b"VmRSS:")
    return int(datos[i + 6:datos.index(b"kB", i)])


def mem_disponible_kib() -> int:
    with open("/proc/meminfo") as f:
        for linea in f:
            if linea.startswith("MemAvailable"):
                return int(linea.split()[1])
    return -1


def puertos_abiertos(puertos=PUERTOS_HDFS) -> list[int]:
    abiertos = []
    for p in puertos:
        with socket.socket() as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", p)) == 0:
                abiertos.append(p)
    return abiertos


def huella(r) -> tuple:
    """Lo que devuelve la consulta (rutas y n.º de resultados), para verificar integridad."""
    return tuple(x["hdfs_path"] for x in r.resultados)


def sha_manifiesto() -> str:
    return hashlib.sha256((ENTREGA2_DIR / "indice" / "manifiesto.json").read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Monitor de condiciones (PowerShell, escribe cada 15 s)
# ---------------------------------------------------------------------------
_PS_MONITOR = r"""
$f = '{csv}'; $latido = '{latido}'; $fin = '{detener}'
$k = 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes'
while (-not (Test-Path $fin)) {{
  if ((Test-Path $latido) -and (((Get-Date) - (Get-Item $latido).LastWriteTime).TotalMinutes -gt 15)) {{ break }}
  try {{
    $p = Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -Filter "Name='_Total'"
    $b = Get-CimInstance Win32_Battery | Select-Object -First 1
    $m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $ac = (Get-ItemProperty $k).ActiveOverlayAcPowerScheme
    $t = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
    $linea = '{{0}}|{{1}}|{{2}}|{{3}}|{{4}}|{{5}}|{{6}}|{{7}}' -f $t, $p.ProcessorFrequency, $p.PercentProcessorPerformance, $p.PercentProcessorTime, $b.BatteryStatus, $b.EstimatedChargeRemaining, $ac, $m.AvailableMBytes
    Add-Content -Path $f -Value $linea -Encoding ascii
  }} catch {{ }}
  Start-Sleep -Seconds 15
}}
"""
CAMPOS_MONITOR = ("utc", "mhz_nominal", "rendimiento_pct", "cpu_pct", "bateria_estado", "bateria_pct", "modo_ac",
                  "windows_disponible_mb")


def ruta_windows(p: Path) -> str:
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()


class Monitor:
    def __init__(self, directorio: Path):
        self.dir = directorio
        self.csv, self.latido, self.fin = directorio / "monitor.csv", directorio / "latido", directorio / "detener"
        self.proc = None

    def iniciar(self, espera_s: float = 40) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fin.unlink(missing_ok=True)
        self.latir()
        ps1 = self.dir / "monitor.ps1"
        ps1.write_text(_PS_MONITOR.format(csv=ruta_windows(self.csv), latido=ruta_windows(self.latido),
                                          detener=ruta_windows(self.fin)), encoding="ascii")
        n0 = len(self._lineas())
        self.proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                      ruta_windows(ps1)], cwd="/mnt/c", stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        t0 = time.time()
        while len(self._lineas()) <= n0:
            if time.time() - t0 > espera_s:
                raise RuntimeError("el monitor de PowerShell no escribió ninguna línea")
            time.sleep(1)

    def latir(self) -> None:
        self.latido.touch()

    def _lineas(self) -> list[str]:
        try:
            return [l for l in self.csv.read_text(encoding="ascii", errors="replace").splitlines() if l.count("|") == 7]
        except FileNotFoundError:
            return []

    def ultima(self) -> dict | None:
        lineas = self._lineas()
        if not lineas:
            return None
        d = dict(zip(CAMPOS_MONITOR, lineas[-1].split("|")))
        try:
            t = datetime.fromisoformat(d["utc"].replace("Z", "+00:00"))
            d["edad_s"] = round((datetime.now(timezone.utc) - t).total_seconds(), 1)
            d["mhz_efectivos"] = round(float(d["mhz_nominal"]) * float(d["rendimiento_pct"]) / 100)
        except (ValueError, KeyError):
            d["edad_s"] = None
        return d

    def detener(self) -> None:
        self.fin.touch()
        if self.proc is not None:
            try:
                self.proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def condiciones(monitor: Monitor, completo: bool = False) -> dict:
    """Estado actual y si es válido para medir (METODOLOGIA.md, Fase 6, E)."""
    m = monitor.ultima()
    c = {"utc": ahora(), "monitor": m, "hdfs_puertos_abiertos": puertos_abiertos(),
         "wsl_mem_disponible_mib": round(mem_disponible_kib() / 1024), "ajuste_reloj": ajuste_reloj()}
    if completo:
        from entorno import resumen_equipo
        c["equipo"] = resumen_equipo()
    motivos = []
    if m is None or m.get("edad_s") is None or m["edad_s"] > EDAD_MAX_MONITOR_S:
        motivos.append("monitor de condiciones sin datos recientes")
    else:
        if m["bateria_estado"] == "1":
            motivos.append("el equipo está con batería (desenchufado)")
        if m["modo_ac"].lower() != MODO_MAXIMO:
            motivos.append(f"modo de energía distinto de Máximo rendimiento ({m['modo_ac'] or 'Equilibrado'})")
    if c["hdfs_puertos_abiertos"]:
        motivos.append(f"HDFS encendido (puertos {c['hdfs_puertos_abiertos']})")
    if mem_disponible_kib() < MEM_MINIMA_KIB:
        motivos.append(f"memoria disponible de WSL < 2 GiB ({c['wsl_mem_disponible_mib']} MiB)")
    c["validas"], c["motivos"] = not motivos, motivos
    return c


def registrar(directorio: Path, evento: str, datos: dict) -> None:
    with open(directorio / "condiciones.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"evento": evento, **datos}, ensure_ascii=False) + "\n")


def checkpoint(directorio: Path, monitor: Monitor, evento: str, extra: dict | None = None,
               completo: bool = False) -> dict:
    monitor.latir()
    c = condiciones(monitor, completo)
    registrar(directorio, evento, {**c, **(extra or {})})
    if not c["validas"]:
        raise Pausa("; ".join(c["motivos"]))
    return c


# ---------------------------------------------------------------------------
# Plan (orden de los pares por ronda) y reanudación
# ---------------------------------------------------------------------------
def plan_de(directorio: Path, pasada: str, reps: int, pares: list, semilla) -> dict:
    if reps % BLOQUE:
        raise ValueError(f"--reps debe ser múltiplo de {BLOQUE}")
    rondas = reps // BLOQUE
    rng = np.random.default_rng(semilla)
    plan = {"pasada": pasada, "reps": reps, "bloque": BLOQUE, "rondas": rondas, "calentamiento": CALENTAMIENTO,
            "top": TOP, "semilla": semilla, "reloj": RELOJ, "pares": [list(p) for p in pares], "argumentos": ARGUMENTOS_CLI,
            "sha256_manifiesto_indice": sha_manifiesto(),
            "ordenes": [rng.permutation(len(pares)).tolist() for _ in range(rondas)]}
    ruta = directorio / "plan.json"
    if ruta.exists():
        viejo = json.loads(ruta.read_text())
        claves = [k for k in plan if k != "creado_utc"]
        distintas = [k for k in claves if viejo.get(k) != json.loads(json.dumps(plan[k]))]
        if distintas:
            raise SystemExit(f"{ruta}: la corrida existente tiene otros parámetros ({distintas}); use otra --corrida")
        return viejo
    plan["creado_utc"] = ahora()
    directorio.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    return plan


def rondas_hechas(directorio: Path, ext: str) -> set[int]:
    return {int(p.stem.split("_")[1]) for p in directorio.glob(f"ronda_*.{ext}")}


# ---------------------------------------------------------------------------
# Pasada de tiempo
# ---------------------------------------------------------------------------
def pasada_tiempo(corrida: Path, reps: int, monitor: Monitor) -> None:
    from buscador import Buscador
    d = corrida / "tiempo"
    plan = plan_de(d, "tiempo", reps, PARES, SEMILLA_BENCHMARK)
    hechas = rondas_hechas(d, "npz")
    if len(hechas) == plan["rondas"]:
        print(f"tiempo: las {plan['rondas']} rondas ya están")
        return
    checkpoint(d, monitor, "inicio", completo=True)
    r0 = estado_proceso()
    t0 = raw_s()
    b = Buscador()
    carga_s = raw_s() - t0
    r1 = estado_proceso()
    sesion = {"utc": ahora(), "carga_indices_s": round(carga_s, 3), "rss_antes_kib": r0["VmRSS"],
              "rss_despues_de_cargar_kib": r1["VmRSS"], "vmhwm_despues_de_cargar_kib": r1["VmHWM"],
              "blas": b.blas, "rondas_ya_hechas": len(hechas)}

    t0 = raw_s()
    esperado = []
    for (m, o, c) in PARES:  # calentamiento: no se registra
        kw = ARGUMENTOS_CLI[c]
        for _ in range(CALENTAMIENTO):
            r = b.buscar(modelo=m, optim=o, top=TOP, **kw)
        esperado.append(huella(r))
    sesion["calentamiento_s"] = round(raw_s() - t0, 1)
    registrar(d, "sesion", sesion)
    print(f"tiempo: índices cargados en {carga_s:.2f} s; calentamiento {sesion['calentamiento_s']} s; "
          f"rondas hechas {len(hechas)}/{plan['rondas']}", flush=True)

    reloj, RAW, mono = time.clock_gettime_ns, _RAW, time.perf_counter_ns
    try:
        for ronda in range(plan["rondas"]):
            if ronda in hechas:
                continue
            t_ronda = raw_s()
            datos = np.zeros((len(PARES), BLOQUE), dtype=np.int64)
            bloques = np.zeros((len(PARES), 2), dtype=np.int64)  # duración del bloque: RAW y MONOTONIC
            for j in plan["ordenes"][ronda]:
                m, o, c = PARES[j]
                kw, buscar, fila = ARGUMENTOS_CLI[c], b.buscar, datos[j]
                r = None
                gc.collect()
                gc.disable()
                try:
                    b_raw, b_mono = reloj(RAW), mono()
                    for i in range(BLOQUE):
                        r = None  # libera el resultado anterior fuera de la región medida
                        t_a = reloj(RAW)
                        r = buscar(modelo=m, optim=o, top=TOP, **kw)
                        t_b = reloj(RAW)
                        fila[i] = t_b - t_a
                    bloques[j] = (reloj(RAW) - b_raw, mono() - b_mono)
                finally:
                    gc.enable()
                if huella(r) != esperado[j]:
                    raise RuntimeError(f"ronda {ronda}, par {PARES[j]}: el resultado cambió respecto del calentamiento")
            dur = raw_s() - t_ronda
            guardar_atomico(d / f"ronda_{ronda:05d}.npz",
                            lambda fh: np.savez(fh, tiempo_ns=datos, bloque_raw_ns=bloques[:, 0],
                                                bloque_monotonic_ns=bloques[:, 1]))
            hechas.add(ronda)
            med = {f"{m}|{o}": round(float(np.median(datos[[k for k, p in enumerate(PARES) if p[:2] == (m, o)]])) / 1e6, 4)
                   for m, o in CONFIGS}
            c = checkpoint(d, monitor, "ronda", {"ronda": ronda, "duracion_s": round(dur, 2), "mediana_ms": med,
                                                 "monotonic_sobre_raw_pct": round(
                                                     (bloques[:, 1].sum() / bloques[:, 0].sum() - 1) * 100, 2)})
            falta = (plan["rondas"] - len(hechas)) * dur
            mon = c["monitor"] or {}
            print(f"tiempo: ronda {ronda + 1}/{plan['rondas']} en {dur:.1f} s | {mon.get('mhz_efectivos')} MHz | "
                  f"faltan ~{falta / 60:.0f} min", flush=True)
    finally:
        b.cerrar()


# ---------------------------------------------------------------------------
# Pasada de RAM (un proceso por configuración)
# ---------------------------------------------------------------------------
def ram_config(corrida: Path, reps: int, modelo: str, optim: str) -> None:
    """Corre en un proceso nuevo: solo los índices de (modelo, optim)."""
    from buscador import Buscador
    d = corrida / "ram" / f"{modelo}_{optim}"
    idx_cfg = CONFIGS.index((modelo, optim))
    pares = [(modelo, optim, c) for c in CONSULTAS_IDS]
    plan = plan_de(d, "ram", reps, pares, [SEMILLA_BENCHMARK, idx_cfg])
    hechas = rondas_hechas(d, "npz")
    if len(hechas) == plan["rondas"]:
        return
    monitor = Monitor(corrida)  # lo inicia el proceso padre; aquí solo se lee y se late
    checkpoint(d, monitor, "inicio")
    r0 = estado_proceso()
    t0 = raw_s()
    b = Buscador(solo=(modelo, optim))
    carga_s = raw_s() - t0
    gc.collect()
    r1 = estado_proceso()
    esperado = []
    for (_, _, c) in pares:
        for _ in range(CALENTAMIENTO):
            r = b.buscar(modelo=modelo, optim=optim, top=TOP, **ARGUMENTOS_CLI[c])
        esperado.append(huella(r))
    r = None
    gc.collect()
    r2 = estado_proceso()
    registrar(d, "sesion", {"utc": ahora(), "carga_indices_s": round(carga_s, 3),
                            "rss_antes_de_cargar_kib": r0["VmRSS"], "rss_despues_de_cargar_kib": r1["VmRSS"],
                            "vmhwm_despues_de_cargar_kib": r1["VmHWM"], "rss_despues_de_calentar_kib": r2["VmRSS"],
                            "vmhwm_despues_de_calentar_kib": r2["VmHWM"], "blas": b.blas,
                            "rondas_ya_hechas": len(hechas)})

    tracemalloc.start()
    traza, reset = tracemalloc.get_traced_memory, tracemalloc.reset_peak
    try:
        for ronda in range(plan["rondas"]):
            if ronda in hechas:
                continue
            t_ronda = raw_s()
            pico = np.zeros((len(pares), BLOQUE), dtype=np.int64)
            neto = np.zeros_like(pico)
            rss = np.zeros_like(pico)
            for j in plan["ordenes"][ronda]:
                kw, buscar = ARGUMENTOS_CLI[pares[j][2]], b.buscar
                fp, fn, fr = pico[j], neto[j], rss[j]
                r = None
                gc.collect()
                gc.disable()
                try:
                    for i in range(BLOQUE):
                        r = None
                        antes = traza()[0]
                        reset()
                        r = buscar(modelo=modelo, optim=optim, top=TOP, **kw)
                        actual, pk = traza()
                        fp[i], fn[i], fr[i] = pk - antes, actual - antes, vmrss_kib()
                finally:
                    gc.enable()
                if huella(r) != esperado[j]:
                    raise RuntimeError(f"ram {modelo}/{optim} ronda {ronda}: el resultado cambió")
            dur = raw_s() - t_ronda
            guardar_atomico(d / f"ronda_{ronda:05d}.npz",
                            lambda fh: np.savez(fh, pico_bytes=pico, neto_bytes=neto, rss_kib=rss))
            hechas.add(ronda)
            checkpoint(d, monitor, "ronda", {"ronda": ronda, "duracion_s": round(dur, 2),
                                             "mediana_pico_kib": round(float(np.median(pico)) / 1024, 2)})
            print(f"ram {modelo}/{optim}: ronda {ronda + 1}/{plan['rondas']} en {dur:.1f} s", flush=True)
    finally:
        tracemalloc.stop()
        b.cerrar()


def pasada_ram(corrida: Path, reps: int, monitor: Monitor) -> None:
    (corrida / "ram").mkdir(parents=True, exist_ok=True)
    checkpoint(corrida / "ram", monitor, "inicio", completo=True)
    for m, o in CONFIGS:
        t0 = raw_s()
        r = subprocess.run([sys.executable, __file__, "_ram_config", "--corrida", corrida.name, "--reps", str(reps),
                            "--modelo", m, "--optim", o])
        if r.returncode == CODIGO_PAUSA:
            raise Pausa(f"pausa en la configuración {m}/{o} (ver condiciones.jsonl)")
        if r.returncode != 0:
            raise RuntimeError(f"la pasada de RAM de {m}/{o} terminó con código {r.returncode}")
        monitor.latir()
        print(f"ram {m}/{o}: listo en {raw_s() - t0:.0f} s", flush=True)


# ---------------------------------------------------------------------------
# Resumen (estadísticas, tablas y estimación)
# ---------------------------------------------------------------------------
ESTADISTICOS = ("MIN", "Q1", "MEDIAN", "Q3", "MAX", "IQR", "MEAN", "STD")


def estadisticas(v: np.ndarray) -> dict:
    v = np.asarray(v, dtype=np.float64)
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return {"MIN": float(v.min()), "Q1": float(q1), "MEDIAN": float(med), "Q3": float(q3), "MAX": float(v.max()),
            "IQR": float(q3 - q1), "MEAN": float(v.mean()), "STD": float(v.std(ddof=1)) if v.size > 1 else 0.0,
            "n": int(v.size)}


def _miles(n: int) -> str:
    """100000 -> '100.000' (separador de miles en español)."""
    return f"{n:,}".replace(",", ".")


def _leer_tiempo(d: Path) -> np.ndarray:
    rondas = sorted(d.glob("ronda_*.npz"))
    return (np.concatenate([np.load(p)["tiempo_ns"] for p in rondas], axis=1) if rondas
            else np.empty((len(PARES), 0)))


def _desvio_monotonic(d: Path) -> float | None:
    """Cuánto más rápido corrió CLOCK_MONOTONIC que MONOTONIC_RAW en los bloques medidos (%)."""
    rondas = sorted(d.glob("ronda_*.npz"))
    if not rondas:
        return None
    raw = sum(int(np.load(p)["bloque_raw_ns"].sum()) for p in rondas)
    mono = sum(int(np.load(p)["bloque_monotonic_ns"].sum()) for p in rondas)
    return (mono / raw - 1) * 100


def _leer_ram(d: Path) -> dict[str, np.ndarray]:
    rondas = sorted(d.glob("ronda_*.npz"))
    if not rondas:
        return {}
    zs = [np.load(p) for p in rondas]
    return {k: np.concatenate([z[k] for z in zs], axis=1) for k in ("pico_bytes", "neto_bytes", "rss_kib")}


def _eventos(d: Path) -> list[dict]:
    ruta = d / "condiciones.jsonl"
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines()] if ruta.exists() else []


def _pared_por_ronda(eventos: list[dict]) -> float:
    """Segundos de pared por ronda con el checkpoint incluido: diferencia entre eventos "ronda"
    consecutivos de una misma sesión (una reanudación no cuenta la espera entre sesiones)."""
    difs, previo = [], None
    for x in eventos:
        if x["evento"] != "ronda":
            previo = None
            continue
        t = datetime.fromisoformat(x["utc"]).timestamp()
        if previo is not None:
            difs.append(t - previo)
        previo = t
    if difs:
        return float(np.mean(difs))
    rs = [x["duracion_s"] for x in eventos if x["evento"] == "ronda"]
    return float(np.mean(rs)) + 2.0


def _tabla_md(titulo: str, filas: list[tuple[str, dict]], fmt: str, primera: str = "Configuración") -> list[str]:
    out = [f"### {titulo}", "", f"| {primera} | " + " | ".join(ESTADISTICOS) + " |",
           "|---|" + "---:|" * len(ESTADISTICOS)]
    for nombre, e in filas:
        out.append(f"| {nombre} | " + " | ".join(format(e[k], fmt) for k in ESTADISTICOS) + " |")
    return out + [""]


def _csv(ruta: Path, filas: list[dict]) -> None:
    import csv
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for f in filas for k in f)))
        w.writeheader()
        w.writerows(filas)


def resumen(corrida: Path, destino: Path, reps_objetivo: int = 100_000) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    md = [f"# Benchmark — corrida `{corrida.name}`", ""]
    t = _leer_tiempo(corrida / "tiempo")
    filas_csv, filas_cfg, filas_par = [], [], []
    if t.shape[1]:
        ms = t / 1e6
        for m, o in CONFIGS:
            idx = [k for k, p in enumerate(PARES) if p[:2] == (m, o)]
            e = estadisticas(ms[idx].ravel())
            filas_cfg.append((NOMBRE[(m, o)], e))
            filas_csv.append({"configuracion": NOMBRE[(m, o)], "modelo": m, "optim": o, "consulta": "A–E",
                              **{k: round(v, 6) if isinstance(v, float) else v for k, v in e.items()}})
            for k in idx:
                e = estadisticas(ms[k])
                filas_par.append((f"{NOMBRE[(m, o)]} | {PARES[k][2]}", e))
                filas_csv.append({"configuracion": NOMBRE[(m, o)], "modelo": m, "optim": o, "consulta": PARES[k][2],
                                  **{kk: round(v, 6) if isinstance(v, float) else v for kk, v in e.items()}})
        n_rep = t.shape[1]
        md += _tabla_md(f"Tabla 1 — Tiempo de respuesta por consulta (ms), {_miles(n_rep)} repeticiones × 5 consultas",
                        filas_cfg, ".3f")
        md += _tabla_md("Anexo — Tiempo por configuración y consulta (ms)", filas_par, ".3f", "Configuración | consulta")
        _csv(destino / "benchmark_tiempo.csv", filas_csv)
        # mediana por ronda (deriva)
        por_ronda = []
        for r in range(t.shape[1] // BLOQUE):
            sl = ms[:, r * BLOQUE:(r + 1) * BLOQUE]
            por_ronda.append({"ronda": r, **{NOMBRE[(m, o)]: round(float(np.median(
                sl[[k for k, p in enumerate(PARES) if p[:2] == (m, o)]])), 4) for m, o in CONFIGS}})
        _csv(destino / "benchmark_tiempo_por_ronda.csv", por_ronda)

    filas_ram_cfg, filas_ram_par, filas_rss_par, base, ram_csv = [], [], [], [], []
    for m, o in CONFIGS:
        d = corrida / "ram" / f"{m}_{o}"
        datos = _leer_ram(d)
        if not datos:
            continue
        kib = datos["pico_bytes"] / 1024
        e = estadisticas(kib.ravel())
        filas_ram_cfg.append((NOMBRE[(m, o)], e))
        ram_csv.append({"medida": "pico_tracemalloc_kib", "configuracion": NOMBRE[(m, o)], "consulta": "A–E", **e})
        for j, c in enumerate(CONSULTAS_IDS):
            e = estadisticas(kib[j])
            filas_ram_par.append((f"{NOMBRE[(m, o)]} | {c}", e))
            ram_csv.append({"medida": "pico_tracemalloc_kib", "configuracion": NOMBRE[(m, o)], "consulta": c, **e})
            e = estadisticas(datos["rss_kib"][j] / 1024)
            filas_rss_par.append((f"{NOMBRE[(m, o)]} | {c}", e))
            ram_csv.append({"medida": "rss_despues_mib", "configuracion": NOMBRE[(m, o)], "consulta": c, **e})
            e = estadisticas(datos["neto_bytes"][j] / 1024)
            ram_csv.append({"medida": "neto_kib", "configuracion": NOMBRE[(m, o)], "consulta": c, **e})
        ses = next((x for x in _eventos(d) if x["evento"] == "sesion"), None)
        if ses:
            base.append({"configuracion": NOMBRE[(m, o)], "carga_indices_s": ses["carga_indices_s"],
                         "rss_despues_de_cargar_mib": round(ses["rss_despues_de_cargar_kib"] / 1024, 1),
                         "rss_despues_de_calentar_mib": round(ses["rss_despues_de_calentar_kib"] / 1024, 1),
                         "vmhwm_mib": round(ses["vmhwm_despues_de_calentar_kib"] / 1024, 1),
                         "rss_tras_ultima_consulta_mib": round(float(datos["rss_kib"][:, -1].max()) / 1024, 1)})
    if filas_ram_cfg:
        n_rep = _leer_ram(corrida / "ram" / "tfidf_ninguna").get("pico_bytes", np.empty((5, 0))).shape[1]
        md += _tabla_md(f"Tabla 1 — RAM por consulta: pico de tracemalloc (KiB), {_miles(n_rep)} repeticiones × 5 consultas",
                        filas_ram_cfg, ".1f")
        md += ["### RSS base por configuración (proceso nuevo con solo sus índices)", "",
               "| Configuración | Carga (s) | RSS tras cargar (MiB) | RSS tras calentar (MiB) | VmHWM (MiB) | RSS tras la última consulta (MiB) |",
               "|---|---:|---:|---:|---:|---:|"]
        md += [f"| {b['configuracion']} | {b['carga_indices_s']:.2f} | {b['rss_despues_de_cargar_mib']} | "
               f"{b['rss_despues_de_calentar_mib']} | {b['vmhwm_mib']} | {b['rss_tras_ultima_consulta_mib']} |"
               for b in base] + [""]
        md += _tabla_md("Anexo — Pico de tracemalloc por configuración y consulta (KiB)", filas_ram_par, ".1f",
                        "Configuración | consulta")
        md += _tabla_md("Anexo — RSS después de cada consulta (MiB)", filas_rss_par, ".1f", "Configuración | consulta")
        _csv(destino / "benchmark_ram.csv", ram_csv)
        _csv(destino / "benchmark_rss_base.csv", base)

    # carga en la pasada de tiempo y condiciones
    ev_t = _eventos(corrida / "tiempo")
    ses_t = [x for x in ev_t if x["evento"] == "sesion"]
    mhz = [x["monitor"]["mhz_efectivos"] for d in [corrida / "tiempo", *sorted((corrida / "ram").glob("*_*"))]
           for x in _eventos(d) if x.get("monitor") and x["monitor"].get("mhz_efectivos")]
    if ses_t:
        md += [f"Carga de todos los índices (pasada de tiempo): {ses_t[0]['carga_indices_s']:.2f} s; RSS tras cargar "
               f"{ses_t[0]['rss_despues_de_cargar_kib'] / 1024:.1f} MiB; BLAS: {ses_t[0]['blas']}", ""]
    desvio = _desvio_monotonic(corrida / "tiempo")
    if desvio is not None:
        md += [f"Reloj: {RELOJ}. En los bloques medidos, CLOCK_MONOTONIC (perf_counter_ns) avanzó "
               f"{desvio:+.2f} % respecto de MONOTONIC_RAW.", ""]
    if mhz:
        md += [f"Frecuencia efectiva de la CPU en los checkpoints: mín {min(mhz)} / mediana {int(np.median(mhz))} / "
               f"máx {max(mhz)} MHz ({len(mhz)} lecturas)", ""]

    # estimación de la corrida completa
    est = {}
    rondas_t = [x["duracion_s"] for x in ev_t if x["evento"] == "ronda"]
    if rondas_t and ses_t:
        n_obj = reps_objetivo // BLOQUE
        por_ronda = _pared_por_ronda(ev_t)
        est["tiempo_ronda_s"] = float(np.mean(rondas_t))
        est["tiempo_ronda_pared_s"] = por_ronda
        est["tiempo_s"] = ses_t[0]["carga_indices_s"] + ses_t[0]["calentamiento_s"] + n_obj * por_ronda
    ram_ronda = {}
    for m, o in CONFIGS:
        ev = _eventos(corrida / "ram" / f"{m}_{o}")
        if any(x["evento"] == "ronda" for x in ev):
            ram_ronda[f"{m}|{o}"] = _pared_por_ronda(ev)
    if ram_ronda:
        n_obj = reps_objetivo // BLOQUE
        est["ram_s"] = sum(n_obj * v + 30 for v in ram_ronda.values())  # + carga y calentamiento
        est["ram_ronda_s"] = ram_ronda
    if est:
        md += [f"### Estimación para {_miles(reps_objetivo)} repeticiones por par", ""]
        if "tiempo_s" in est:
            md.append(f"- Pasada de tiempo: {est['tiempo_ronda_s']:.1f} s medidos por ronda "
                      f"({est['tiempo_ronda_pared_s']:.1f} s de pared con el checkpoint) → ~{est['tiempo_s'] / 3600:.1f} h")
        if "ram_s" in est:
            md.append(f"- Pasada de RAM: ~{est['ram_s'] / 3600:.1f} h (s por ronda: "
                      + ", ".join(f"{k} {v:.1f}" for k, v in est["ram_ronda_s"].items()) + ")")
        if "tiempo_s" in est and "ram_s" in est:
            md.append(f"- **Total: ~{(est['tiempo_s'] + est['ram_s']) / 3600:.1f} h**")
        md.append("")
        (destino / "benchmark_estimacion.json").write_text(json.dumps(est, indent=1))
    texto = "\n".join(md) + "\n"
    (destino / "benchmark_resumen.md").write_text(texto, encoding="utf-8")
    print(texto)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=("tiempo", "ram", "resumen", "todo", "_ram_config"))
    ap.add_argument("--corrida", default="completa", help="nombre de la carpeta en salidas/benchmark/")
    ap.add_argument("--reps", type=int, default=100_000)
    ap.add_argument("--modelo")
    ap.add_argument("--optim")
    ap.add_argument("--destino", help="carpeta del resumen (por defecto informe/ si la corrida es 'completa')")
    a = ap.parse_args(argv)
    corrida = BENCH_DIR / a.corrida
    destino = Path(a.destino) if a.destino else (ENTREGA2_DIR / "informe" if a.corrida == "completa"
                                                 else corrida / "resumen")
    try:
        if a.accion == "_ram_config":
            ram_config(corrida, a.reps, a.modelo, a.optim)
            return 0
        if a.accion == "resumen":
            resumen(corrida, destino)
            return 0
        monitor = Monitor(corrida)
        monitor.iniciar()
        try:
            if a.accion in ("tiempo", "todo"):
                pasada_tiempo(corrida, a.reps, monitor)
            if a.accion in ("ram", "todo"):
                pasada_ram(corrida, a.reps, monitor)
        finally:
            monitor.detener()
        if a.accion == "todo":
            resumen(corrida, destino)
        return 0
    except Pausa as e:
        print(f"PAUSA: {e}. Lo medido quedó guardado; corrija la condición y repita el mismo comando para "
              "reanudar.", file=sys.stderr, flush=True)
        return CODIGO_PAUSA


if __name__ == "__main__":
    sys.exit(main())
