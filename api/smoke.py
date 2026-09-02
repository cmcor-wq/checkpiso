"""Endpoint temporal de validación en vivo para desplegar en Vercel.

No es parte de la arquitectura final de PisoCheck (que sigue siendo CLI,
ver spec §11) — es solo el arnés para probar geocoder/catastro/osm/
opendata_vlc contra las APIs reales desde un sitio con salida a internet,
ya que el sandbox donde se escribió el resto del proyecto la tiene
bloqueada por política de organización.

GET /api/smoke -> JSON con los resultados para Garbí 24 y Av. Burjassot 71,
comparados contra el ground truth conocido (ver tests/fixtures/ground_truth.py).

Recomendado borrar este endpoint (o el proyecto de Vercel) una vez validado,
es público y sin autenticación.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pisocheck.geocoder import geocode
from pisocheck.sources import catastro, opendata_vlc, osm

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


async def probar_caso(caso: dict) -> dict:
    resultado: dict = {"nombre": caso["nombre"], "checks": []}
    esperado = caso["esperado"]
    addr = None

    try:
        addr = await geocode(caso["direccion"])
        lat_ok = abs(addr.lat - esperado["lat"]) < 0.01
        lng_ok = abs(addr.lng - esperado["lng"]) < 0.01
        resultado["geocoder"] = {
            "lat": addr.lat,
            "lng": addr.lng,
            "municipio": addr.municipio,
            "distrito": addr.distrito,
            "barrio": addr.barrio,
        }
        resultado["checks"].append({"nombre": "coordenadas", "ok": lat_ok and lng_ok})
    except Exception as e:  # noqa: BLE001
        resultado["checks"].append(
            {"nombre": "geocoder", "ok": False, "error": f"{type(e).__name__}: {e}"}
        )

    try:
        cat = await catastro.consulta_dnp(
            caso["provincia"], caso["municipio"], caso["calle"], caso["numero"]
        )
        resultado["catastro"] = cat
        resultado["checks"].append(
            {
                "nombre": "ref_catastral",
                "ok": cat.get("ref_catastral") == esperado.get("ref_catastral"),
                "obtenido": cat.get("ref_catastral"),
                "esperado": esperado.get("ref_catastral"),
            }
        )
        resultado["checks"].append(
            {
                "nombre": "anio_construccion",
                "ok": cat.get("anio_construccion") == esperado.get("anio_construccion"),
                "obtenido": cat.get("anio_construccion"),
            }
        )
    except Exception as e:  # noqa: BLE001
        resultado["checks"].append(
            {"nombre": "catastro", "ok": False, "error": f"{type(e).__name__}: {e}"}
        )

    if addr is not None:
        try:
            farm = await osm.farmacias(addr.lat, addr.lng, radius_m=1000)
            resultado["osm_farmacias"] = {
                "count": len(farm),
                "mas_cercana_m": farm[0]["distancia_m"] if farm else None,
            }
            resultado["checks"].append({"nombre": "overpass", "ok": True})
        except Exception as e:  # noqa: BLE001
            resultado["checks"].append(
                {"nombre": "overpass", "ok": False, "error": f"{type(e).__name__}: {e}"}
            )

        if caso.get("distrito_opendata"):
            try:
                quejas = await opendata_vlc.get_quejas(caso["distrito_opendata"])
                resultado["opendata_vlc"] = quejas
                resultado["checks"].append({"nombre": "opendata_vlc", "ok": True})
            except Exception as e:  # noqa: BLE001
                resultado["checks"].append(
                    {"nombre": "opendata_vlc", "ok": False, "error": f"{type(e).__name__}: {e}"}
                )

    return resultado


async def run_all() -> list[dict]:
    return [await probar_caso(caso) for caso in CASOS]


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            resultados = asyncio.run(run_all())
            body = json.dumps(
                {"ok": True, "resultados": resultados}, ensure_ascii=False, indent=2
            ).encode("utf-8")
            status = 200
        except Exception as e:  # noqa: BLE001
            body = json.dumps(
                {"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False
            ).encode("utf-8")
            status = 500

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
