import pytest

from pisocheck.models import AddressData
from pisocheck.sources.catastro import (
    CatastroError,
    consulta_dnp,
    merge_into_address,
)
from tests.fixtures.ground_truth import GARBI24

# XML de ejemplo con la forma documentada de Consulta_DNPPP para Garbí 24.
# ref catastral esperada: pc1+pc2+car+cc1+cc2 = 8081706YJ1688S0003FU
GARBI24_DNP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<consulta_dnp xmlns="http://www.catastro.meh.es/">
  <control><cuerr>0</cuerr></control>
  <bico>
    <bi>
      <idbi>
        <rc>
          <pc1>8081706</pc1>
          <pc2>YJ1688S</pc2>
          <car>0003</car>
          <cc1>F</cc1>
          <cc2>U</cc2>
        </rc>
      </idbi>
      <dt>
        <np>VALENCIA</np>
        <nm>TORRENT</nm>
      </dt>
      <ldt>CL GARBI 24 46900 TORRENT (VALENCIA)</ldt>
      <debi>
        <luso>Residencial</luso>
        <sfc>152</sfc>
        <ant>1980</ant>
      </debi>
    </bi>
  </bico>
</consulta_dnp>
"""

CATASTRO_ERROR_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<consulta_dnp xmlns="http://www.catastro.meh.es/">
  <control><cuerr>1</cuerr></control>
  <lerr><err><des>No se ha localizado el inmueble</des></err></lerr>
</consulta_dnp>
"""


async def test_consulta_dnp_garbi24(httpx_mock):
    httpx_mock.add_response(method="GET", content=GARBI24_DNP_XML)

    data = await consulta_dnp("VALENCIA", "TORRENT", "GARBI", "24")

    assert data["ref_catastral"] == GARBI24["ref_catastral"]
    assert data["superficie_construida"] == GARBI24["superficie_construida"]
    assert data["anio_construccion"] == GARBI24["anio_construccion"]


async def test_consulta_dnp_error(httpx_mock):
    httpx_mock.add_response(method="GET", content=CATASTRO_ERROR_XML)

    with pytest.raises(CatastroError):
        await consulta_dnp("VALENCIA", "DIRECCION", "INEXISTENTE", "0")


def test_merge_into_address_only_overwrites_present_fields():
    base = AddressData(raw=GARBI24["raw"], lat=GARBI24["lat"], lng=GARBI24["lng"], municipio="Torrent")
    catastro_data = {
        "ref_catastral": GARBI24["ref_catastral"],
        "superficie_construida": GARBI24["superficie_construida"],
        "anio_construccion": GARBI24["anio_construccion"],
        "uso": "Residencial",
    }

    merged = merge_into_address(base, catastro_data)

    assert merged.ref_catastral == GARBI24["ref_catastral"]
    assert merged.superficie_construida == GARBI24["superficie_construida"]
    assert merged.lat == GARBI24["lat"]  # no debe tocar campos no catastrales
