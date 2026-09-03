"""Geocodificación: dirección en texto libre -> lat/lng + municipio/distrito/barrio.

Usa Nominatim (OpenStreetMap), gratuito y sin autenticación, pero con una
política de uso estricta: máximo 1 req/seg y un User-Agent identificable
(ver NOMINATIM_USER_AGENT en config.py / .env).

Nota sobre distrito/barrio: Nominatim no tiene un campo fijo "distrito" o
"barrio" — depende de cómo esté mapeado cada municipio en OSM. Este módulo
hace un best-effort tomando los campos más plausibles de `address` y no debe
tratarse como fuente autoritativa de la división administrativa; para
Valencia ciudad, sources/opendata_vlc.py necesita el nombre de distrito
oficial (p. ej. "CAMPANAR"), así que conviene verificar/objetivo ese valor
contra la lista real de distritos cuando haya acceso de red.
"""

from __future__ import annotations

import httpx

from pisocheck.config import HTTP_TIMEOUT_SECONDS, NOMINATIM_USER_AGENT
from pisocheck.models import AddressData

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Orden de preferencia para mapear los campos "address" de Nominatim a
# nuestros conceptos de distrito/barrio/municipio/provincia.
_BARRIO_KEYS = ("neighbourhood", "suburb", "quarter", "city_block")
_DISTRITO_KEYS = ("city_district", "borough", "district")
_MUNICIPIO_KEYS = ("city", "town", "municipality", "village")
_PROVINCIA_KEYS = ("state_district", "county", "province")


def _first_present(address: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = address.get(key)
        if value:
            return value
    return None


class GeocodeError(RuntimeError):
    """La dirección no se pudo geocodificar."""


def _simplificar(raw_address: str) -> str | None:
    """'Carrer del Garbí 24, 2, Torrent' -> 'Carrer del Garbí 24, Torrent'.

    Quita los segmentos intermedios (piso, puerta...) que a veces hacen que
    Nominatim no encuentre nada aunque la dirección exista — visto en
    producción: la búsqueda con "2," en medio fallaba, sin el "2" funciona.
    Devuelve None si no hay nada que simplificar (2 segmentos o menos).
    """
    partes = [p.strip() for p in raw_address.split(",") if p.strip()]
    if len(partes) <= 2:
        return None
    return f"{partes[0]}, {partes[-1]}"


async def _buscar(query: str, *, client: httpx.AsyncClient) -> dict | None:
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "es",
    }
    resp = await client.get(
        NOMINATIM_URL, params=params, headers={"User-Agent": NOMINATIM_USER_AGENT}
    )
    resp.raise_for_status()
    results = resp.json()
    return results[0] if results else None


async def geocode(raw_address: str, *, client: httpx.AsyncClient | None = None) -> AddressData:
    """Convierte una dirección en texto libre a AddressData (campos base).

    Si la búsqueda con la dirección completa no encuentra nada, reintenta
    una vez con una versión simplificada (sin piso/puerta) antes de darse
    por vencido.
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        result = await _buscar(raw_address, client=client)
        if result is None:
            simplificada = _simplificar(raw_address)
            if simplificada:
                result = await _buscar(simplificada, client=client)
    finally:
        if owns_client:
            await client.aclose()

    if result is None:
        raise GeocodeError(f"No se encontraron resultados para: {raw_address!r}")

    address = result.get("address", {})

    municipio = _first_present(address, _MUNICIPIO_KEYS)
    if not municipio:
        raise GeocodeError(f"No se pudo determinar el municipio para: {raw_address!r}")

    return AddressData(
        raw=raw_address,
        lat=float(result["lat"]),
        lng=float(result["lon"]),
        municipio=municipio,
        provincia=_first_present(address, _PROVINCIA_KEYS),
        distrito=_first_present(address, _DISTRITO_KEYS),
        barrio=_first_present(address, _BARRIO_KEYS),
    )
