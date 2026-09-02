import pytest

from pisocheck import config
from pisocheck.sources import places


async def test_nearby_sin_api_key_devuelve_none(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", None)

    result = await places.nearby(39.4866, -0.3877, "pharmacy")

    assert result is None


async def test_nearby_con_api_key_parsea_resultados(monkeypatch, httpx_mock):
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", "fake-key-for-tests")
    httpx_mock.add_response(
        method="GET",
        json={
            "status": "OK",
            "results": [
                {
                    "name": "Farmacia Les Tendetes",
                    "geometry": {"location": {"lat": 39.4870, "lng": -0.3877}},
                    "rating": 4.5,
                    "opening_hours": {"open_now": True},
                    "types": ["pharmacy", "health"],
                }
            ],
        },
    )

    result = await places.farmacias(39.4866, -0.3877)

    assert result is not None
    assert len(result) == 1
    assert result[0]["nombre"] == "Farmacia Les Tendetes"
    assert result[0]["distancia_m"] is not None


async def test_nearby_zero_results_no_es_error(monkeypatch, httpx_mock):
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", "fake-key-for-tests")
    httpx_mock.add_response(method="GET", json={"status": "ZERO_RESULTS", "results": []})

    result = await places.bares(39.4866, -0.3877)

    assert result == []


async def test_nearby_error_status_lanza_excepcion(monkeypatch, httpx_mock):
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", "fake-key-for-tests")
    httpx_mock.add_response(
        method="GET",
        json={"status": "REQUEST_DENIED", "error_message": "clave inválida"},
    )

    with pytest.raises(places.PlacesError):
        await places.bares(39.4866, -0.3877)
