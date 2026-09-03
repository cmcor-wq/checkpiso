"""OpenStreetMap — Overpass API.

Cubre: farolas (iluminación), ocio nocturno, zonas verdes, transporte,
colegios, farmacias, supermercados y aparcamiento. Sin autenticación, pero
Overpass tiene límites de uso agresivos (timeouts, rate limiting por IP) —
en producción conviene tener un servidor Overpass propio o de respaldo si
el volumen de consultas crece.
"""

from __future__ import annotations

import re

import httpx

from pisocheck.config import HTTP_TIMEOUT_SECONDS
from pisocheck.utils import haversine_m

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Busca rangos horarios tipo "08:00-23:30" dentro del tag OSM
# "opening_hours". Es un parseo best-effort, no un parser completo de la
# sintaxis de opening_hours (que admite excepciones, festivos, etc.).
_TIME_RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _cierra_tarde(opening_hours: str | None) -> bool | None:
    """¿Este horario incluye algún cierre después de las 23:00?

    True/False si se pudo determinar, None si no hay tag `opening_hours`
    o no se pudo interpretar (duda razonable, se penaliza menos en el
    scoring en vez de tratarse como "no cierra tarde").
    """
    if not opening_hours:
        return None
    if "24/7" in opening_hours:
        return True

    matches = _TIME_RANGE_RE.findall(opening_hours)
    if not matches:
        return None

    for _open_h, _open_m, close_h, _close_m in matches:
        close_h = int(close_h)
        # >=23:00, o de madrugada (00-04h, indica que el rango cruza
        # medianoche, p.ej. "12:00-01:00").
        if close_h >= 23 or close_h <= 4:
            return True
    return False


class OSMError(RuntimeError):
    """Error consultando Overpass."""


def _coords(element: dict) -> tuple[float, float] | None:
    """Nodo -> (lat, lon) directo; way/relation -> requiere 'out center;'."""
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    center = element.get("center")
    if center:
        return center["lat"], center["lon"]
    return None


async def _run_query(
    query_body: str, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    query = f"[out:json][timeout:25];{query_body}out center;"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        resp = await client.post(OVERPASS_URL, data={"data": query})
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            await client.aclose()

    return data.get("elements", [])


async def query_around(
    lat: float,
    lng: float,
    radius_m: int,
    tag_filter: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Consulta nodos/ways/relaciones que cumplan `tag_filter` en un radio.

    `tag_filter` es la parte Overpass QL entre corchetes, p.ej.
    '["amenity"~"bar|pub|nightclub"]'.
    """
    body = (
        f'(node{tag_filter}(around:{radius_m},{lat},{lng});'
        f'way{tag_filter}(around:{radius_m},{lat},{lng}););'
    )
    elements = await _run_query(body, client=client)

    results = []
    for el in elements:
        coords = _coords(el)
        if coords is None:
            continue
        el_lat, el_lng = coords
        results.append(
            {
                "id": el.get("id"),
                "nombre": el.get("tags", {}).get("name"),
                "tags": el.get("tags", {}),
                "lat": el_lat,
                "lon": el_lng,
                "distancia_m": round(haversine_m(lat, lng, el_lat, el_lng)),
            }
        )
    return sorted(results, key=lambda r: r["distancia_m"])


async def farolas(lat: float, lng: float, radius_m: int = 500, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["highway"="street_lamp"]', **kw)


async def ocio_nocturno(lat: float, lng: float, radius_m: int = 500, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["amenity"~"bar|pub|nightclub"]', **kw)


async def ocio_tardio(lat: float, lng: float, radius_m: int = 300, **kw) -> list[dict]:
    """Bares, pubs, discotecas y restaurantes — proxy de ruido nocturno.

    Añade `cierra_tarde` (True/False/None) a cada resultado, inferido del
    tag OSM `opening_hours`. Sin mapa de ruido oficial (Lnight), es la
    mejor aproximación disponible: un local que cierra después de las
    23:00 cerca de la vivienda es la fuente más probable de ruido nocturno.
    """
    resultados = await query_around(
        lat, lng, radius_m, '["amenity"~"bar|pub|nightclub|restaurant"]', **kw
    )
    for r in resultados:
        r["cierra_tarde"] = _cierra_tarde(r["tags"].get("opening_hours"))
    return resultados


async def transporte(lat: float, lng: float, radius_m: int = 800, **kw) -> list[dict]:
    metro = await query_around(
        lat, lng, radius_m, '["station"~"subway|light_rail"]', **kw
    )
    bus = await query_around(lat, lng, radius_m, '["highway"="bus_stop"]', **kw)
    for stop in metro:
        stop["tipo"] = "metro"
    for stop in bus:
        stop["tipo"] = "bus"
    return sorted(metro + bus, key=lambda r: r["distancia_m"])


async def zonas_verdes(lat: float, lng: float, radius_m: int = 1000, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["leisure"~"park|garden"]', **kw)


async def colegios(lat: float, lng: float, radius_m: int = 1000, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["amenity"="school"]', **kw)


async def farmacias(lat: float, lng: float, radius_m: int = 1000, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["amenity"="pharmacy"]', **kw)


async def supermercados(lat: float, lng: float, radius_m: int = 1000, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["shop"~"supermarket|convenience"]', **kw)


async def parking(lat: float, lng: float, radius_m: int = 800, **kw) -> list[dict]:
    return await query_around(lat, lng, radius_m, '["amenity"="parking"]', **kw)
