"""Tests unitarios del tokenizador (Fase 2).

Contrato que debe cumplir ``src/tokenizer.py`` (una sola función para documentos y consultas):

- ``tokenizar(valor, llave=None) -> list[str]``
    * Documento: se llama con la llave FITS original (``llave="ESO DET EXP TYPE"``).
    * Consulta: se llama sin llave (``tokenizar("exp type normal")``); por eso la
      regla 1 (que actúa solo sobre llaves) no elimina "ins" de la consulta D.
- ``tokenizar_header(header: dict) -> list[str]``: concatena ``tokenizar(v, llave=k)``.
- Funciones por regla, aplicadas en orden 1→5:
    ``regla1_llave``, ``regla2_nulos``, ``regla3_identificadores``,
    ``regla4_fechas_checksums``, ``regla5_normalizar``, y el predicado
    ``es_identificador_hardware``.

Los tests de la sección "consultas oficiales" fijan también los DESAJUSTES conocidos
(``filt``, ``ins``, ``opti`` no existen en los documentos; ``normal`` es polisémico).
No deben "arreglarse" en el tokenizador: se analizan en el informe.
"""
import pytest

from tokenizer import (
    es_identificador_hardware,
    regla1_llave,
    regla2_nulos,
    regla3_identificadores,
    regla4_fechas_checksums,
    regla5_normalizar,
    tokenizar,
    tokenizar_header,
)


# ---------------------------------------------------------------------------
# Regla 1: llave unida al valor; se eliminan los prefijos ESO, DET e INS de la llave
# ---------------------------------------------------------------------------
class TestRegla1:
    @pytest.mark.parametrize(
        "llave, esperado",
        [
            ("ESO DET EXP TYPE", "EXP TYPE"),
            ("ESO INS OPTI3 NAME", "OPTI3 NAME"),
            ("ESO INS FILT1 NAME", "FILT1 NAME"),
            ("ESO DPR TYPE", "DPR TYPE"),
            ("INSTRUME", "INSTRUME"),  # "INS" solo como palabra completa
            ("DATE-OBS", "DATE-OBS"),
            ("OBJECT", "OBJECT"),
        ],
    )
    def test_elimina_prefijos(self, llave, esperado):
        assert regla1_llave(llave) == esperado

    def test_llave_y_valor_quedan_juntos(self):
        assert tokenizar("Normal", llave="ESO DET EXP TYPE") == ["exp", "type", "normal"]

    def test_eso_en_el_valor_no_se_elimina(self):
        # La regla 1 actúa solo sobre la llave; "ESO" dentro del valor se conserva.
        assert tokenizar("ESO-VLT-DIC.TCS", llave="ESO TEL DID") == [
            "tel", "did", "eso", "vlt", "dic", "tcs",
        ]

    def test_consulta_sin_llave_no_aplica_regla1(self):
        assert tokenizar("ins opti 1.6x11") == ["ins", "opti", "1_6x11"]


# ---------------------------------------------------------------------------
# Regla 2: eliminar "UNKNOWN" y "not set" (sin distinguir mayúsculas)
# ---------------------------------------------------------------------------
class TestRegla2:
    def test_unknown(self):
        assert tokenizar("UNKNOWN", llave="OBSERVER") == ["observer"]

    def test_not_set_dentro_de_un_valor(self):
        # Caso real: TELESCOP='Tel name not set' en 1.592 archivos.
        assert tokenizar("Tel name not set", llave="TELESCOP") == ["telescop", "tel", "name"]

    @pytest.mark.parametrize("texto", ["unknown", "Unknown", "NOT SET", "Not Set", "not set"])
    def test_insensible_a_mayusculas(self, texto):
        assert regla2_nulos(f"a {texto} b").split() == ["a", "b"]

    def test_no_toca_otros_valores(self):
        assert regla2_nulos("LAMP,AFC") == "LAMP,AFC"


# ---------------------------------------------------------------------------
# Regla 3: "x" entre números y guiones de identificadores de hardware -> "_"
# ---------------------------------------------------------------------------
class TestRegla3:
    @pytest.mark.parametrize(
        "valor, esperado",
        [
            ("1.0x12.6", "1_0x12_6"),
            ("1.6x11", "1_6x11"),
            ("5.0x11", "5_0x11"),
            ("0.5x11", "0_5x11"),
            ("CCD57-10IE", "CCD57_10IE"),
            ("e2v CC44-82", "e2v CC44_82"),
            ("MIT/LL CCID-20", "MIT/LL CCID_20"),
        ],
    )
    def test_reemplaza_puntuacion_por_guion_bajo(self, valor, esperado):
        assert regla3_identificadores(valor) == esperado

    @pytest.mark.parametrize(
        "token, esperado",
        [
            ("CCD57-10IE", True),
            ("CC44-82", True),
            ("CCID-20", True),
            ("ESO-VLT-U3", True),          # segmentos alfanuméricos, letra y dígito
            ("FULLY-OPEN", False),         # sin dígito
            ("ADC-RG", False),             # sin dígito
            ("2026-09-05", False),         # fecha ISO (además sin letra)
            ("2026-09-05T22", False),      # fecha ISO con hora: excluida explícitamente
            ("5e-05", False),              # notación científica: excluida explícitamente
            ("1.8e-05", False),            # notación científica con punto
            ("XSHOOTER_ICS-402729", False),  # "_" no es alfanumérico
            ("60.A-9820", False),          # "." no es alfanumérico
        ],
    )
    def test_definicion_identificador_hardware(self, token, esperado):
        assert es_identificador_hardware(token) is esperado

    def test_regla3_no_captura_fechas_iso(self):
        fecha = "2026-09-05T22:54:01.123"
        assert regla3_identificadores(fecha) == fecha

    def test_regla3_no_captura_notacion_cientifica(self):
        assert regla3_identificadores("1.8e-05") == "1.8e-05"
        assert regla3_identificadores("5e-05") == "5e-05"

    def test_sin_x_no_aplica(self):
        # "Pin_0.5" no tiene "x" entre números: el "." se trata en la regla 5.
        assert tokenizar("Pin_0.5", llave="ESO INS OPTI3 NAME") == ["opti3", "name", "pin_0", "5"]

    def test_tokens_completos(self):
        assert tokenizar("1.0x12.6", llave="ESO INS OPTI3 NAME") == ["opti3", "name", "1_0x12_6"]
        assert tokenizar("e2v CC44-82", llave="ESO DET CHIP1 NAME") == [
            "chip1", "name", "e2v", "cc44_82",
        ]
        assert tokenizar("FULLY-OPEN", llave="ESO TEL DOME STATUS") == [
            "tel", "dome", "status", "fully", "open",
        ]
        assert tokenizar("1.8e-05", llave="ESO DET CHIP PXSPACE") == [
            "chip", "pxspace", "1", "8e", "05",
        ]


# ---------------------------------------------------------------------------
# Regla 4: eliminar el VALOR de fechas ISO y de CHECKSUM/DATASUM (la llave se conserva)
# ---------------------------------------------------------------------------
class TestRegla4:
    def test_fecha_iso_completa(self):
        assert tokenizar("2026-09-05T22:54:01.123", llave="DATE-OBS") == ["date", "obs"]

    def test_fecha_iso_solo_dia(self):
        assert tokenizar("2026-09-05", llave="ESO INS DATE") == ["date"]

    def test_fecha_incrustada_en_arcfile(self):
        assert tokenizar("XSHOO.2026-09-04T01:43:37.983.fits", llave="ARCFILE") == [
            "arcfile", "xshoo", "fits",
        ]

    def test_checksum(self):
        assert tokenizar("LoXNMoUMLoUMLoUM", llave="CHECKSUM") == ["checksum"]

    def test_datasum_numerico(self):
        assert tokenizar("3899192641", llave="DATASUM") == ["datasum"]

    def test_regla4_directa(self):
        assert regla4_fechas_checksums("iekCiZiBidiBiZiB", llave="CHECKSUM").strip() == ""
        assert regla4_fechas_checksums("a 2026-09-05T00:00:00 b").split() == ["a", "b"]

    def test_orden_3_luego_4_no_deja_restos_de_fecha(self):
        tokens = tokenizar("2026-09-05T22:54:01", llave="DATE")
        assert tokens == ["date"]
        assert not any("2026" in t for t in tokens)

    def test_fechas_tambien_se_eliminan_en_consultas(self):
        assert tokenizar("flat 2026-09-05") == ["flat"]


# ---------------------------------------------------------------------------
# Regla 5: puntuación -> espacio, se conserva "_", minúsculas, separar por espacios
# ---------------------------------------------------------------------------
class TestRegla5:
    def test_coma_se_vuelve_espacio(self):
        assert tokenizar("FLAT,SKY", llave="ESO DPR TYPE") == ["dpr", "type", "flat", "sky"]

    def test_conserva_guion_bajo(self):
        assert tokenizar("z_prime", llave="ESO INS FILT1 NAME") == ["filt1", "name", "z_prime"]

    def test_minusculas_y_separacion(self):
        assert regla5_normalizar("A/B (C)  D") == ["a", "b", "c", "d"]

    def test_valor_con_parentesis_y_punto(self):
        assert tokenizar("60.A-9820(A)", llave="ESO OBS PROG ID") == [
            "obs", "prog", "id", "60", "a", "9820", "a",
        ]

    def test_guion_de_llave(self):
        assert tokenizar("61287.07", llave="MJD-OBS") == ["mjd", "obs", "61287", "07"]

    def test_valores_no_texto(self):
        assert tokenizar(True, llave="SIMPLE") == ["simple", "true"]
        assert tokenizar(5.0, llave="EXPTIME") == ["exptime", "5", "0"]
        assert tokenizar(None, llave="OBJECT") == ["object"]
        assert tokenizar("") == []


# ---------------------------------------------------------------------------
# tokenizar_header: misma función aplicada campo a campo
# ---------------------------------------------------------------------------
def test_tokenizar_header_concatena_campos():
    header = {"ESO DPR TYPE": "FLAT,SKY", "DATE-OBS": "2026-09-05T22:54:01.123", "CHECKSUM": "abc"}
    esperado = (
        tokenizar("FLAT,SKY", llave="ESO DPR TYPE")
        + tokenizar("2026-09-05T22:54:01.123", llave="DATE-OBS")
        + tokenizar("abc", llave="CHECKSUM")
    )
    assert tokenizar_header(header) == esperado == [
        "dpr", "type", "flat", "sky", "date", "obs", "checksum",
    ]


# ---------------------------------------------------------------------------
# Las 5 consultas oficiales (misma función que los documentos)
# ---------------------------------------------------------------------------
CONSULTAS = {
    "A": ("flat sky", ["flat", "sky"]),
    "B": ("filt b", ["filt", "b"]),
    "C": ("exp type normal", ["exp", "type", "normal"]),
    "D": ("ins opti 1.6x11", ["ins", "opti", "1_6x11"]),
    "E": ("", []),
}


@pytest.mark.parametrize("cid", sorted(CONSULTAS))
def test_tokens_de_consultas_oficiales(cid):
    texto, esperado = CONSULTAS[cid]
    assert tokenizar(texto) == esperado


def test_consulta_E_sin_texto():
    assert tokenizar(None) == []
    assert tokenizar("   ") == []


class TestCoberturaConsultaDocumento:
    """Fija qué tokens de cada consulta aparecen en un documento relevante típico."""

    def test_A_todos_los_tokens_presentes(self):
        doc = set(tokenizar_header({"ESO DPR TYPE": "FLAT,SKY"}))
        assert set(tokenizar("flat sky")) <= doc

    def test_B_filt_no_existe_en_documentos(self):
        doc = set(tokenizar_header({"ESO INS FILT1 NAME": "B"}))
        assert "b" in doc
        assert "filt" not in doc and "filt1" in doc  # desajuste conocido: no se corrige

    def test_C_tokens_presentes_y_polisemia(self):
        doc_relevante = set(tokenizar_header({"ESO DET EXP TYPE": "Normal"}))
        assert set(tokenizar("exp type normal")) <= doc_relevante
        # "normal" también proviene de otras llaves (p. ej. INS SWSIM=NORMAL, en todos los archivos)
        assert "normal" in tokenizar("NORMAL", llave="ESO INS SWSIM")
        assert "type" in tokenizar("Normal", llave="ESO DET FRAM TYPE")

    def test_D_ins_y_opti_no_existen_en_documentos(self):
        doc = set(tokenizar_header({"ESO INS OPTI3 NAME": "1.6x11"}))
        assert "1_6x11" in doc
        assert "ins" not in doc  # eliminado por la regla 1
        assert "opti" not in doc and "opti3" in doc  # desajuste conocido: no se corrige
