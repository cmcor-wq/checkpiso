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
