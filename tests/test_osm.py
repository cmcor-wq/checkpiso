from pisocheck.sources.osm import _cierra_tarde, farmacias, ocio_tardio, transporte
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


def test_cierra_tarde_sin_horario_es_none():
    assert _cierra_tarde(None) is None
    assert _cierra_tarde("") is None


def test_cierra_tarde_24_7():
    assert _cierra_tarde("24/7") is True


def test_cierra_tarde_cierre_despues_de_23h():
    assert _cierra_tarde("Mo-Su 18:00-23:30") is True


def test_cierra_tarde_cruza_medianoche():
    assert _cierra_tarde("Th-Sa 20:00-02:00") is True


def test_cierra_tarde_cierre_temprano():
    assert _cierra_tarde("Mo-Su 08:00-22:00") is False


def test_cierra_tarde_horario_no_interpretable():
    assert _cierra_tarde("closed on public holidays") is None


async def test_ocio_tardio_marca_cierra_tarde(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        json={
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": LAT + 0.0005,
                    "lon": LNG,
                    "tags": {"name": "Bar Tarde", "amenity": "bar", "opening_hours": "Mo-Su 18:00-03:00"},
                },
                {
                    "type": "node",
                    "id": 2,
                    "lat": LAT + 0.001,
                    "lon": LNG,
                    "tags": {"name": "Restaurante Temprano", "amenity": "restaurant", "opening_hours": "Mo-Su 12:00-22:00"},
                },
                {
                    "type": "node",
                    "id": 3,
                    "lat": LAT + 0.0007,
                    "lon": LNG,
                    "tags": {"name": "Pub Sin Horario", "amenity": "pub"},
                },
            ]
        },
    )

    result = await ocio_tardio(LAT, LNG)

    por_nombre = {r["nombre"]: r["cierra_tarde"] for r in result}
    assert por_nombre["Bar Tarde"] is True
    assert por_nombre["Restaurante Temprano"] is False
    assert por_nombre["Pub Sin Horario"] is None
