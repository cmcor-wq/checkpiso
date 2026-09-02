import pytest

from pisocheck.sources.solar import SolarError, get_solar_data

PVGIS_RESPONSE_BURJASSOT71 = {
    "inputs": {"location": {"latitude": 39.4866, "longitude": -0.3877}},
    "outputs": {
        "monthly": {
            "fixed": [
                {"month": m, "E_d": 3.0 + (m % 4) * 0.5, "E_m": 90.0}
                for m in range(1, 13)
            ]
        },
        "totals": {"fixed": {"E_d": 4.8, "E_m": 146.0, "E_y": 1752.0}},
    },
}


async def test_get_solar_data_parsea_horas_dia(httpx_mock):
    httpx_mock.add_response(method="GET", json=PVGIS_RESPONSE_BURJASSOT71)

    data = await get_solar_data(39.4866, -0.3877)

    assert data["horas_sol_dia"] == 4.8
    assert len(data["horas_sol_mensual"]) == 12


async def test_get_solar_data_usa_e_y_si_falta_e_d(httpx_mock):
    response = {
        "outputs": {
            "monthly": {"fixed": []},
            "totals": {"fixed": {"E_y": 1825.0}},  # 1825/365 = 5.0
        }
    }
    httpx_mock.add_response(method="GET", json=response)

    data = await get_solar_data(39.4866, -0.3877)

    assert data["horas_sol_dia"] == 5.0


async def test_get_solar_data_forma_inesperada_lanza_error(httpx_mock):
    httpx_mock.add_response(method="GET", json={"algo": "inesperado"})

    with pytest.raises(SolarError):
        await get_solar_data(39.4866, -0.3877)
