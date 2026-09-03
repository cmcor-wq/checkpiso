from pisocheck.address_parsing import extraer_calle_numero
from tests.fixtures.ground_truth import BURJASSOT71, GARBI24


def test_extraer_calle_numero_garbi24():
    calle, numero = extraer_calle_numero(GARBI24["raw"])
    assert calle == "GARBI"
    assert numero == "24"


def test_extraer_calle_numero_burjassot71():
    calle, numero = extraer_calle_numero(BURJASSOT71["raw"])
    assert calle == "BURJASSOT"
    assert numero == "71"


def test_extraer_calle_numero_sin_numero_devuelve_none():
    calle, numero = extraer_calle_numero("Calle Sin Número, Valencia")
    assert calle is None
    assert numero is None


def test_extraer_calle_numero_prefijo_plaza():
    calle, numero = extraer_calle_numero("Plaza del Ayuntamiento 1, Valencia")
    assert calle == "AYUNTAMIENTO"
    assert numero == "1"
