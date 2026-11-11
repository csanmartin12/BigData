"""Consultas oficiales A–E, criterios de relevancia y filtros de MongoDB.

Los criterios de relevancia son los de la Fase 0 (METODOLOGIA.md) y se evalúan sobre el
``header`` original de cada documento. Sirven para *marcar* resultados, nunca para construir el
índice ni para elegir parámetros.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


def filtro_caja_coordenadas(ra_min: float, ra_max: float, dec_min: float, dec_max: float) -> dict:
    """Caja RA × DEC en grados (bordes incluidos), resuelta con el índice compuesto ``ra_dec``.

    Es un filtro por intervalos sobre los valores originales del header, como en la Tabla 9
    del Informe 1, y no una consulta geoespacial: los bordes son meridianos y paralelos
    exactos. Los documentos sin coordenadas no tienen ``search.ra``/``search.dec`` y quedan
    fuera.
    """
    return {
        "search.ra": {"$gte": ra_min, "$lte": ra_max},
        "search.dec": {"$gte": dec_min, "$lte": dec_max},
    }


def filtro_dia(fecha: str) -> dict:
    """DATE-OBS dentro del día UTC ``AAAA-MM-DD`` (índice ``date_obs``)."""
    ini = datetime.fromisoformat(fecha).replace(tzinfo=timezone.utc)
    return {"search.date_obs": {"$gte": ini, "$lt": ini + timedelta(days=1)}}


# Prueba E del enunciado: RA ∈ [84, 85] y DEC ∈ [−70, −69] (solo filtro numérico).
PRUEBA_E = {"ra_min": 84.0, "ra_max": 85.0, "dec_min": -70.0, "dec_max": -69.0}


def _en_caja(h: dict, c: dict = PRUEBA_E) -> bool:
    ra, dec = h.get("RA"), h.get("DEC")
    return (isinstance(ra, (int, float)) and isinstance(dec, (int, float))
            and c["ra_min"] <= ra <= c["ra_max"] and c["dec_min"] <= dec <= c["dec_max"])


@dataclass(frozen=True)
class Consulta:
    id: str
    texto: str
    criterio: str
    es_relevante: Callable[[dict], bool]
    filtro_mongo: dict | None = None  # parte estructurada de la consulta híbrida


CONSULTAS = {
    "A": Consulta("A", "flat sky", "ESO DPR TYPE=FLAT,SKY y DATE-OBS 2026-09-05",
                  lambda h: h.get("ESO DPR TYPE") == "FLAT,SKY" and str(h.get("DATE-OBS", "")).startswith("2026-09-05"),
                  filtro_mongo=filtro_dia("2026-09-05")),
    "B": Consulta("B", "filt b", "ESO INS FILT1 NAME=B", lambda h: h.get("ESO INS FILT1 NAME") == "B"),
    "C": Consulta("C", "exp type normal", "ESO DET EXP TYPE=Normal", lambda h: h.get("ESO DET EXP TYPE") == "Normal"),
    "D": Consulta("D", "ins opti 1.6x11", "ESO INS OPTI3 NAME=1.6x11",
                  lambda h: h.get("ESO INS OPTI3 NAME") == "1.6x11"),
    "E": Consulta("E", "", "RA en [84,85] y DEC en [-70,-69] (solo numérica)", _en_caja,
                  filtro_mongo=filtro_caja_coordenadas(**PRUEBA_E)),
}

# Argumentos de la CLI (``Buscador.buscar``) para cada consulta oficial: los que usan la prueba
# preliminar, el benchmark y la precisión. A: texto + día de DATE-OBS; E: solo la caja RA × DEC.
ARGUMENTOS_CLI = {
    "A": {"texto": "flat sky", "fecha_desde": "2026-09-05", "fecha_hasta": "2026-09-05"},
    "B": {"texto": "filt b"},
    "C": {"texto": "exp type normal"},
    "D": {"texto": "ins opti 1.6x11"},
    "E": {"ra_min": 84, "ra_max": 85, "dec_min": -70, "dec_max": -69},
}

# Campos que deciden la relevancia (se muestran junto a los resultados)
CAMPOS_RELEVANCIA = ["ESO DPR TYPE", "DATE-OBS", "ESO INS FILT1 NAME", "ESO DET EXP TYPE", "ESO INS OPTI3 NAME"]
