"""Validación en vivo contra las APIs reales — Garbí 24 y Av. Burjassot 71.

Este script NO usa mocks: hace peticiones HTTP de verdad. Solo tiene
sentido ejecutarlo en un entorno con salida a internet (no funciona en el
sandbox de Claude Code donde se escribió el resto del proyecto — ahí la
política de red bloquea estos dominios).

Uso:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pisocheck.geocoder import geocode
from pisocheck.sources import catastro, opendata_vlc, osm

OK = "✓"
FAIL = "✗"

CASOS = [
    {
        "nombre": "Garbí 24, Torrent",
        "direccion": "Carrer del Garbí 24, 2, Torrent",
        "provincia": "VALENCIA",
        "municipio": "TORRENT",
        "calle": "GARBI",
        "numero": "24",
        "esperado": {
            "lat": 39.4332,
            "lng": -0.4680,
            "ref_catastral": "8081706YJ1688S0003FU",
            "superficie_construida": 152,
            "anio_construccion": 1980,
        },
    },
    {
        "nombre": "Av. Burjassot 71, Valencia",
        "direccion": "Av. de Burjassot 71, Valencia",
        "provincia": "VALENCIA",
        "municipio": "VALENCIA",
        "calle": "BURJASSOT",
        "numero": "71",
        "distrito_opendata": "CAMPANAR",
        "esperado": {
            "lat": 39.4866,
            "lng": -0.3877,
            "ref_catastral": "4742904YJ2744B",
            "anio_construccion": 1975,
        },
    },
]


def check(label: str, ok: bool, detalle: str = "") -> None:
    marca = OK if ok else FAIL
    print(f"  {marca} {label}{': ' + detalle if detalle else ''}")


async def probar_caso(caso: dict) -> None:
    print(f"\n=== {caso['nombre']} ===")
    esperado = caso["esperado"]

    # 1. Geocoder
    addr = None
    try:
        addr = await geocode(caso["direccion"])
        print(f"  Geocodificado: {addr.lat}, {addr.lng} · {addr.municipio} · "
              f"distrito={addr.distrito!r} barrio={addr.barrio!r}")
        lat_ok = abs(addr.lat - esperado["lat"]) < 0.01
        lng_ok = abs(addr.lng - esperado["lng"]) < 0.01
        check("Coordenadas dentro de ~1km del valor esperado", lat_ok and lng_ok)
    except Exception as e:  # noqa: BLE001 — smoke test, cualquier fallo debe reportarse y seguir
        check("Geocoder", False, f"{type(e).__name__}: {e}")

    # 2. Catastro
    try:
        cat = await catastro.consulta_dnp(
            caso["provincia"], caso["municipio"], caso["calle"], caso["numero"]
        )
        print(f"  Catastro: {cat}")
        check(
            "Referencia catastral coincide",
            cat.get("ref_catastral") == esperado.get("ref_catastral"),
            f"obtenido={cat.get('ref_catastral')!r} esperado={esperado.get('ref_catastral')!r}",
        )
        if esperado.get("superficie_construida"):
            check(
                "Superficie construida coincide",
                cat.get("superficie_construida") == esperado["superficie_construida"],
                f"obtenido={cat.get('superficie_construida')}",
            )
        check(
            "Año de construcción coincide",
            cat.get("anio_construccion") == esperado.get("anio_construccion"),
            f"obtenido={cat.get('anio_construccion')}",
        )
    except Exception as e:  # noqa: BLE001
        check("Catastro", False, f"{type(e).__name__}: {e}")

    if addr is None:
        return

    # 3. OSM / Overpass — solo comprobamos que responde y trae algo razonable
    try:
        farm = await osm.farmacias(addr.lat, addr.lng, radius_m=1000)
        print(f"  OSM farmacias en 1km: {len(farm)} encontradas"
              f"{' · más cercana a ' + str(farm[0]['distancia_m']) + 'm' if farm else ''}")
        check("Overpass responde con datos", True)
    except Exception as e:  # noqa: BLE001 — smoke test, queremos ver cualquier fallo
        check("OSM/Overpass", False, f"{type(e).__name__}: {e}")

    # 4. Open Data Valencia (solo aplica a Valencia ciudad)
    if caso.get("distrito_opendata"):
        try:
            quejas = await opendata_vlc.get_quejas(caso["distrito_opendata"])
            print(f"  Open Data VLC quejas en {caso['distrito_opendata']}: "
                  f"{quejas['total']} (últimos 12 meses) · breakdown={quejas['breakdown']}")
            check("Open Data VLC responde con datos", True)
        except Exception as e:  # noqa: BLE001
            check("Open Data VLC", False, str(e))


async def main() -> None:
    for caso in CASOS:
        await probar_caso(caso)
    print(
        "\nRevisa arriba cualquier ✗ — indica un desajuste entre lo que asumí de cada "
        "API (basado en su documentación) y lo que realmente devuelve. Pega la salida "
        "completa de este script de vuelta para que pueda corregir el parser que falle."
    )


if __name__ == "__main__":
    asyncio.run(main())
