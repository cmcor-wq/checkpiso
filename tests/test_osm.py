from pisocheck.sources.osm import farmacias, transporte
from tests.fixtures.ground_truth import BURJASSOT71

LAT, LNG = BURJASSOT71["lat"], BURJASSOT71["lng"]


async def test_farmacias_ordenadas_por_distancia(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        json={
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": LAT + 0.01,  # ~1.1km más lejos
                    "lon": LNG,
                    "tags": {"name": "Farmacia Lejana", "amenity": "pharmacy"},
                },
                {
                    "type": "node",
                    "id": 2,
                    "lat": LAT + 0.001,  # ~110m
                    "lon": LNG,
                    "tags": {"name": "Farmacia Cercana", "amenity": "pharmacy"},
                },
            ]
        },
    )

    result = await farmacias(LAT, LNG, radius_m=1500)

    assert len(result) == 2
    assert result[0]["nombre"] == "Farmacia Cercana"
    assert result[0]["distancia_m"] < result[1]["distancia_m"]


async def test_transporte_combina_metro_y_bus(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        json={
            "elements": [
                {"type": "node", "id": 10, "lat": LAT + 0.003, "lon": LNG, "tags": {"station": "subway"}}
            ]
        },
    )
    httpx_mock.add_response(
        method="POST",
        json={
            "elements": [
                {"type": "node", "id": 11, "lat": LAT + 0.0005, "lon": LNG, "tags": {"highway": "bus_stop"}}
            ]
        },
    )

    result = await transporte(LAT, LNG)

    tipos = {stop["tipo"] for stop in result}
    assert tipos == {"metro", "bus"}
    assert result[0]["tipo"] == "bus"  # el bus está más cerca en este fixture
