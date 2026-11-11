"""Tokenizador de la Entrega 2 (Fase 2): una sola función para documentos y consultas.

Aplica las 5 reglas del enunciado en orden, con las interpretaciones de METODOLOGIA.md
("Decisiones de preprocesamiento"):

1. ``regla1_llave``: la llave va unida al valor; se eliminan las palabras **iniciales** ``ESO``,
   ``DET`` e ``INS`` de la llave (como palabras completas: ``INSTRUME`` se conserva). En
   los datos, esas palabras solo aparecen al comienzo de las llaves.
2. ``regla2_nulos``: se eliminan las subcadenas ``unknown`` y ``not set``, sin distinguir
   mayúsculas.
3. ``regla3_identificadores``: en cada *fragmento* (secuencia maximal de ``[A-Za-z0-9_.-]``):
   - "x entre números": si el fragmento completo es ``\\d+(\\.\\d+)?x\\d+(\\.\\d+)?``, sus ``.``
     pasan a ``_`` (``1.6x11`` → ``1_6x11``);
   - identificador de hardware (``es_identificador_hardware``): sus ``-`` pasan a ``_``.
4. ``regla4_fechas_checksums``: se elimina el valor de las fechas ISO (en cualquier posición) y
   el valor completo de ``CHECKSUM`` y ``DATASUM``. La llave se conserva.
5. ``regla5_normalizar``: toda puntuación pasa a espacio (se conserva ``_``), minúsculas y
   separación por espacios.

Las reglas 2–4 actúan sobre el valor; la 1 sobre la llave; la 5 sobre ambos. Las consultas se
tokenizan con la misma función, sin llave: la regla 1 no se les aplica, por eso ``ins`` de la
consulta D se conserva.
"""
from __future__ import annotations

import re

PALABRAS_INICIALES_LLAVE = frozenset({"ESO", "DET", "INS"})
LLAVES_SIN_VALOR = frozenset({"CHECKSUM", "DATASUM"})

_RE_NULOS = re.compile(r"unknown|not set", re.IGNORECASE)
_RE_FRAGMENTO = re.compile(r"[A-Za-z0-9_.\-]+")
_RE_X_ENTRE_NUMEROS = re.compile(r"\d+(?:\.\d+)?x\d+(?:\.\d+)?")
_RE_INICIO_FECHA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_RE_CIENTIFICA = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)[eE][+-]?\d+")
_RE_SEGMENTO_ALFANUM = re.compile(r"[A-Za-z0-9]+")
_RE_FECHA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}(?::\d{2}(?::\d{2}(?:\.\d+)?)?)?)?")
_RE_PUNTUACION = re.compile(r"[^0-9A-Za-z_\s]")


# ---------------------------------------------------------------------------
# Regla 1
# ---------------------------------------------------------------------------
def regla1_llave(llave: str) -> str:
    palabras = llave.split()
    i = 0
    while i < len(palabras) and palabras[i] in PALABRAS_INICIALES_LLAVE:
        i += 1
    return " ".join(palabras[i:])


# ---------------------------------------------------------------------------
# Regla 2
# ---------------------------------------------------------------------------
def regla2_nulos(texto: str) -> str:
    return _RE_NULOS.sub(" ", texto)


# ---------------------------------------------------------------------------
# Regla 3
# ---------------------------------------------------------------------------
def clasificar_fragmento_guion(fragmento: str) -> str:
    """Por qué un fragmento con guion es o no identificador de hardware.

    Devuelve ``fecha``, ``cientifica``, ``segmento no alfanumerico``, ``sin letra``,
    ``sin digito`` o ``HW`` (en ese orden de prioridad, como el prototipo de la Fase 0).
    """
    if _RE_INICIO_FECHA_ISO.match(fragmento):
        return "fecha"
    if _RE_CIENTIFICA.fullmatch(fragmento):
        return "cientifica"
    if not all(_RE_SEGMENTO_ALFANUM.fullmatch(s) for s in fragmento.split("-")):
        return "segmento no alfanumerico"
    if not any(c.isalpha() for c in fragmento):
        return "sin letra"
    if not any(c.isdigit() for c in fragmento):
        return "sin digito"
    return "HW"


def es_identificador_hardware(fragmento: str) -> bool:
    """Segmentos alfanuméricos unidos por guiones, con al menos una letra y un dígito; se
    excluyen las fechas ISO (``AAAA-MM-DD…``) y la notación científica (``1.8e-05``)."""
    return "-" in fragmento and clasificar_fragmento_guion(fragmento) == "HW"


def _regla3_fragmento(m: re.Match) -> str:
    f = m.group(0)
    if _RE_X_ENTRE_NUMEROS.fullmatch(f):
        return f.replace(".", "_")
    if es_identificador_hardware(f):
        return f.replace("-", "_")
    return f


def regla3_identificadores(texto: str) -> str:
    return _RE_FRAGMENTO.sub(_regla3_fragmento, texto)


# ---------------------------------------------------------------------------
# Regla 4
# ---------------------------------------------------------------------------
def regla4_fechas_checksums(texto: str, llave: str | None = None) -> str:
    if llave is not None and llave.strip().upper() in LLAVES_SIN_VALOR:
        return ""
    return _RE_FECHA_ISO.sub(" ", texto)


# ---------------------------------------------------------------------------
# Regla 5
# ---------------------------------------------------------------------------
def regla5_normalizar(texto: str) -> list[str]:
    return _RE_PUNTUACION.sub(" ", texto).lower().split()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def valor_a_texto(valor) -> str:
    """Valores tipados del header (bool/int/float/str) o ``None`` → texto."""
    if valor is None:
        return ""
    return str(valor)  # True → "True", 5.0 → "5.0", 1.8e-05 → "1.8e-05"


def tokenizar(valor, llave: str | None = None) -> list[str]:
    """Tokens de un par llave-valor (documento) o de un texto sin llave (consulta)."""
    texto = valor_a_texto(valor)
    texto = regla2_nulos(texto)
    texto = regla3_identificadores(texto)
    texto = regla4_fechas_checksums(texto, llave=llave)
    tokens_llave = regla5_normalizar(regla1_llave(llave)) if llave is not None else []
    return tokens_llave + regla5_normalizar(texto)


def tokenizar_header(header: dict) -> list[str]:
    tokens: list[str] = []
    for llave, valor in header.items():
        tokens.extend(tokenizar(valor, llave=llave))
    return tokens
