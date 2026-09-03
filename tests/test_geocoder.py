import pytest

from pisocheck.geocoder import GeocodeError, geocode
from tests.fixtures.ground_truth import GARBI24


async def test_geocode_garbi24(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        json=[
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
        ],
    )

    result = await geocode(GARBI24["raw"])

    assert result.lat == pytest.approx(GARBI24["lat"])
    assert result.lng == pytest.approx(GARBI24["lng"])
    assert result.municipio == "Torrent"
    assert result.barrio == "Centro Torrent"


@pytest.mark.anyio
async def test_geocode_no_results_raises(httpx_mock):
    httpx_mock.add_response(method="GET", json=[])

    with pytest.raises(GeocodeError):
        await geocode("Dirección que no existe en ningún sitio 99999")


async def test_geocode_reintenta_sin_piso_si_la_busqueda_completa_falla(httpx_mock):
    # Visto en producción: Nominatim no encuentra "Carrer del Garbí 24, 2,
    # Torrent" (con el piso en medio) pero sí "Carrer del Garbí 24, Torrent".
    httpx_mock.add_response(method="GET", json=[])  # 1er intento: dirección completa
    httpx_mock.add_response(  # 2º intento: simplificada (sin "2,")
        method="GET",
        json=[
            {
                "lat": str(GARBI24["lat"]),
                "lon": str(GARBI24["lng"]),
                "address": {"city": "Torrent", "neighbourhood": "Centro Torrent"},
            }
        ],
    )

    result = await geocode(GARBI24["raw"])

    assert result.raw == GARBI24["raw"]  # conserva la dirección original del usuario
    assert result.municipio == "Torrent"
    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert "2%2C" not in str(requests[1].url) and "2," not in str(requests[1].url)
