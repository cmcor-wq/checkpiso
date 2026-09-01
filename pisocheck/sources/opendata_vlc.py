"""Open Data Valencia — dataset de quejas y sugerencias ciudadanas.

Solo cubre el municipio de Valencia ciudad (tiene distritos oficiales); no
sirve para Torrent ni el resto de municipios, que no tienen este dataset.

⚠️ Igual que en catastro.py: no ha sido posible validar en vivo el nombre
exacto del dataset ni de los campos "materia"/"fecha_alta" contra la API
real desde este entorno (sin acceso de red). Están tomados literalmente del
documento de especificación; conviene confirmarlos con una llamada real
antes de dar los resultados por buenos.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from pisocheck.config import HTTP_TIMEOUT_SECONDS

BASE_URL = (
    "https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "total-castellano/records"
)

# Materias relevantes para los factores de "quejas vecinales" y "limpieza".
MATERIAS_RUIDO = ("RUIDO",)
MATERIAS_LIMPIEZA = ("LIMPIEZA VIA PUBLICA", "RESIDUOS")
MATERIAS_ALUMBRADO = ("ALUMBRADO",)


class OpenDataVLCError(RuntimeError):
    """Error consultando Open Data Valencia."""


def _build_where(distrito: str, materias: tuple[str, ...] | None, since: date) -> str:
    clauses = [f'distrito="{distrito.upper()}"', f"fecha_alta >= date'{since.isoformat()}'"]
    if materias:
        materia_clause = " OR ".join(f'materia="{m}"' for m in materias)
        clauses.append(f"({materia_clause})")
    return " AND ".join(clauses)


async def get_quejas(
    distrito: str,
    *,
    materias: tuple[str, ...] | None = None,
    months_back: int = 12,
    limit: int = 100,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Cuenta quejas/sugerencias de un distrito en los últimos `months_back` meses.

    Devuelve {"total": int, "breakdown": {materia: count, ...}, "distrito": str}.
    """
    since = date.today() - timedelta(days=30 * months_back)  # noqa: DTZ011 (fecha local, no datetime)
    params = {
        "where": _build_where(distrito, materias, since),
        "limit": limit,
        "order_by": "fecha_alta desc",
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            await client.aclose()

    results = data.get("results", [])
    breakdown: dict[str, int] = {}
    for record in results:
        materia = record.get("materia", "SIN_CLASIFICAR")
        breakdown[materia] = breakdown.get(materia, 0) + 1

    return {
        "total": data.get("total_count", len(results)),
        "breakdown": breakdown,
        "distrito": distrito.upper(),
    }
