"""PVGIS (EU Joint Research Centre) — producción solar / horas de sol.

Sin autenticación. Se usa la salida de un sistema fotovoltaico de 1 kWp
orientado al sur como proxy de "horas de sol equivalentes al día"
(numéricamente, la energía diaria en kWh de un sistema de 1 kWp bajo
condiciones estándar coincide con las "peak sun hours" del lugar).

⚠️ No conocemos la orientación real del edificio (no está en AddressData),
así que se asume sur por defecto — es una aproximación, no la orientación
real de cada vivienda. Sin acceso de red en este entorno tampoco ha sido
posible validar el esquema JSON exacto de la respuesta; el parser acepta
variaciones razonables pero puede necesitar ajuste con una llamada real.
"""

from __future__ import annotations

import httpx

from pisocheck.config import HTTP_TIMEOUT_SECONDS

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"


class SolarError(RuntimeError):
    """PVGIS no devolvió datos utilizables."""


async def get_solar_data(
    lat: float,
    lng: float,
    *,
    peakpower: float = 1.0,
    loss: float = 14.0,
    aspect: float = 0.0,  # 0 = sur, en la convención de PVGIS
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Devuelve {"horas_sol_dia": float, "horas_sol_mensual": [12 floats]}."""
    params = {
        "lat": lat,
        "lon": lng,
        "peakpower": peakpower,
        "loss": loss,
        "aspect": aspect,
        "outputformat": "json",
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        resp = await client.get(PVGIS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            await client.aclose()

    try:
        outputs = data["outputs"]
        totals = outputs["totals"]["fixed"]
        monthly = outputs["monthly"]["fixed"]
    except KeyError as e:
        raise SolarError(f"Respuesta de PVGIS con forma inesperada: falta {e}") from e

    horas_sol_dia = totals.get("E_d")
    if horas_sol_dia is None:
        e_y = totals.get("E_y")
        if e_y is None:
            raise SolarError("PVGIS no devolvió E_d ni E_y")
        horas_sol_dia = e_y / 365

    horas_sol_mensual = [m.get("E_d") for m in monthly]

    return {
        "horas_sol_dia": round(horas_sol_dia, 2),
        "horas_sol_mensual": [round(h, 2) if h is not None else None for h in horas_sol_mensual],
    }
