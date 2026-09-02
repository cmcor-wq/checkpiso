"""Google Places API — Nearby Search.

Requiere GOOGLE_PLACES_API_KEY (de pago, con cuenta de facturación en
Google Cloud). Sin clave, todas las funciones devuelven `None` — el motor
de scoring interpreta `None` como "sin datos" y excluye el factor de la
media en vez de fallar (ver config.py y scoring/engine.py).

⚠️ Google tiene planes de retirar esta API "legacy" en favor de "Places API
(New)" — revisar antes de depender de esto en producción a largo plazo.
"""

from __future__ import annotations

import httpx

from pisocheck import config
from pisocheck.utils import haversine_m

NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


class PlacesError(RuntimeError):
    """Error consultando Google Places."""


async def nearby(
    lat: float,
    lng: float,
    place_type: str,
    *,
    radius_m: int = 500,
    client: httpx.AsyncClient | None = None,
) -> list[dict] | None:
    """Busca establecimientos de `place_type` (taxonomía de Google Places).

    Devuelve None si no hay API key configurada (degradación graceful).
    Devuelve lista (posiblemente vacía) de dicts con nombre/distancia/
    abierto_ahora/rating si sí hay clave.
    """
    if not config.has_google_places():
        return None

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": place_type,
        "key": config.GOOGLE_PLACES_API_KEY,
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS)
    try:
        resp = await client.get(NEARBY_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            await client.aclose()

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        raise PlacesError(f"Google Places devolvió status={status}: {data.get('error_message')}")

    results = []
    for r in data.get("results", []):
        loc = r.get("geometry", {}).get("location", {})
        r_lat, r_lng = loc.get("lat"), loc.get("lng")
        results.append(
            {
                "nombre": r.get("name"),
                "lat": r_lat,
                "lon": r_lng,
                "distancia_m": round(haversine_m(lat, lng, r_lat, r_lng)) if r_lat else None,
                "rating": r.get("rating"),
                "abierto_ahora": r.get("opening_hours", {}).get("open_now"),
                "tipos": r.get("types", []),
            }
        )
    return sorted(results, key=lambda r: r["distancia_m"] or 9999)


async def bares(lat: float, lng: float, **kw) -> list[dict] | None:
    return await nearby(lat, lng, "bar", **kw)


async def farmacias(lat: float, lng: float, **kw) -> list[dict] | None:
    return await nearby(lat, lng, "pharmacy", **kw)


async def supermercados(lat: float, lng: float, **kw) -> list[dict] | None:
    return await nearby(lat, lng, "supermarket", **kw)


async def colegios(lat: float, lng: float, **kw) -> list[dict] | None:
    return await nearby(lat, lng, "school", **kw)


async def parking(lat: float, lng: float, **kw) -> list[dict] | None:
    return await nearby(lat, lng, "parking", **kw)
