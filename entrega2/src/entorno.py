"""Estado del equipo al medir (notebook): corriente/batería y plan de energía de Windows.

Se guarda junto a cada medición para poder descartar las tomadas en malas condiciones
(METODOLOGIA.md, "Condiciones de medición").
"""
from __future__ import annotations

import os
import platform
import subprocess

_PS = (
    "$b = Get-CimInstance Win32_Battery | Select-Object -First 1; "
    "$k = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Power\\User\\PowerSchemes'; "
    "Write-Output ('{0}|{1}|{2}|{3}' -f $b.BatteryStatus, $b.EstimatedChargeRemaining, "
    "$k.ActiveOverlayAcPowerScheme, $k.ActiveOverlayDcPowerScheme); "
    "powercfg /getactivescheme"
)

# "Modo de energía" de Windows 11 (capa sobre el plan de powercfg). Sin valor = Equilibrado.
_MODOS = {
    "": "Equilibrado",
    "00000000-0000-0000-0000-000000000000": "Equilibrado",
    "ded574b5-45a0-4f42-8737-46345c09c238": "Máximo rendimiento",
    "961cc777-2547-4f9d-8174-7d86181b8a7a": "Máxima eficiencia energética",
}


def estado_energia() -> dict:
    """Corriente/batería, modo de energía de Windows 11 (en corriente y en batería) y plan.

    ``Win32_Battery.BatteryStatus``: 1 = descargando (batería), 2 = conectado a la corriente.
    """
    out = {"en_corriente": None, "bateria_pct": None, "modo_ac": None, "modo_dc": None, "plan": None}
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", _PS], capture_output=True,
                           timeout=20, cwd="/mnt/c")
        lineas = [l.strip() for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        estado, pct, ac, dc = (x.strip() for x in lineas[0].split("|"))
        out["en_corriente"] = estado != "1" if estado else None
        out["bateria_pct"] = int(pct) if pct else None
        out["modo_ac"] = _MODOS.get(ac.lower(), ac)
        out["modo_dc"] = _MODOS.get(dc.lower(), dc)
        if len(lineas) > 1 and "(" in lineas[1]:
            out["plan"] = lineas[1].rsplit("(", 1)[1].rstrip(")")
    except Exception as e:  # noqa: BLE001 — informativo; no debe interrumpir una medición
        out["error"] = str(e)
    return out


def condiciones_validas(energia: dict) -> bool:
    """Enchufado y en "Máximo rendimiento" (METODOLOGIA.md, "Condiciones de medición")."""
    return energia.get("en_corriente") is True and energia.get("modo_ac") == "Máximo rendimiento"


_PS_MEM = (
    "$m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; "
    "Write-Output ('{0}|{1}|{2}|{3}|{4}' -f $m.AvailableMBytes, $m.CacheBytes, "
    "$m.StandbyCacheCoreBytes, $m.StandbyCacheNormalPriorityBytes, $m.StandbyCacheReserveBytes)"
)


def memoria_windows() -> dict:
    """Memoria de Windows en MB. La lista standby es la caché de archivos de Windows, que es lo
    que puede retener los ZIP leídos por 9P entre corridas. Es un total, no se puede ver por
    archivo."""
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", _PS_MEM], capture_output=True,
                           timeout=20, cwd="/mnt/c")
        disp, cache, core, normal, reserva = (int(x) for x in r.stdout.decode().strip().split("|"))
        return {"disponible_mb": disp, "cache_mb": round(cache / 2**20),
                "standby_mb": round((core + normal + reserva) / 2**20)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def resumen_equipo() -> dict:
    return {
        "host": platform.node(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "cpus_visibles": os.cpu_count(),
        "energia": estado_energia(),
        "memoria_windows": memoria_windows(),
    }
