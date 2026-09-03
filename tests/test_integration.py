"""Pipeline completo (geocoder -> catastro -> fuentes -> scoring -> HTML)
para Garbí 24, con todas las llamadas HTTP mockeadas — prueba que las
piezas de las Sesiones 1-3 encajan entre sí, no la precisión de cada
fuente por separado (eso ya está cubierto en sus tests individuales).
"""

from pisocheck.main import analizar_direccion
from pisocheck.reports.html_report import render_html
from tests.fixtures.ground_truth import GARBI24

NOMINATIM_JSON = [
    {
        "lat": str(GARBI24["lat"]),
        "lon": str(GARBI24["lng"]),
        "address": {
            "road": "Carrer del Garbí",
            "house_number": "24",
            "city": "Torrent",
            "neighbourhood": "Centro Torrent",
            "state_district": "Valencia/València",
            "postcode": "46900",
            "country": "España",
        },
    }
]

CATASTRO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<consulta_dnp xmlns="http://www.catastro.meh.es/">
  <control><cuerr>0</cuerr></control>
  <bico>
    <bi>
      <idbi><rc><pc1>8081706</pc1><pc2>YJ1688S</pc2><car>0003</car><cc1>F</cc1><cc2>U</cc2></rc></idbi>
      <ldt>CL GARBI 24 46900 TORRENT (VALENCIA)</ldt>
      <debi><luso>Residencial</luso><sfc>152</sfc><ant>1980</ant></debi>
    </bi>
  </bico>
</consulta_dnp>
"""

OVERPASS_JSON = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": GARBI24["lat"] + 0.001,
            "lon": GARBI24["lng"],
            "tags": {"name": "Elemento genérico"},
        }
    ]
}

PVGIS_JSON = {
    "outputs": {
        "monthly": {"fixed": [{"month": m, "E_d": 4.5} for m in range(1, 13)]},
        "totals": {"fixed": {"E_d": 4.5, "E_y": 1642.5}},
    }
}


async def test_pipeline_completo_garbi24(httpx_mock):
    httpx_mock.add_response(method="GET", json=NOMINATIM_JSON)  # Nominatim
    httpx_mock.add_response(method="GET", content=CATASTRO_XML)  # Catastro
    for _ in range(10):  # 10 llamadas Overpass (ver _recolectar_fuentes en main.py)
        httpx_mock.add_response(method="POST", json=OVERPASS_JSON)
    httpx_mock.add_response(method="GET", json=PVGIS_JSON)  # PVGIS

    report = await analizar_direccion(GARBI24["raw"])

    assert report.address.ref_catastral == GARBI24["ref_catastral"]
    assert report.address.anio_construccion == GARBI24["anio_construccion"]
    # Torrent no es Valencia ciudad -> sin Open Data VLC.
    assert report.get_factor("quejas_vecinales") is None
    assert report.get_factor("limpieza_zona") is None
    # El resto de factores basados en OSM/PVGIS sí deberían estar.
    assert report.get_factor("transporte") is not None
    assert report.get_factor("sol_orientacion") is not None
    assert 0 <= report.score_global <= 10

    html = render_html(report)
    assert GARBI24["raw"] in html
    assert GARBI24["ref_catastral"] in html
