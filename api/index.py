"""Único punto de entrada Python para Vercel.

Vercel, al detectar `pyproject.toml` en la raíz, exige un solo entrypoint
por proyecto (ver `[tool.vercel]` en pyproject.toml) — por eso los dos
endpoints que antes eran archivos separados (api/analizar.py, api/smoke.py)
viven ahora en el mismo `handler`, distinguidos por `?modo=`.

GET /api/index?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent
    -> informe HTML real (pipeline completo: main.analizar_direccion).
    Admite &vs=Otra+direccion para comparar dos pisos.

GET /api/index?modo=smoke
    -> JSON de diagnóstico: geocoder/catastro/osm/opendata_vlc contra
    Garbí 24 y Av. Burjassot 71, comparado con el ground truth conocido.
    Útil si /api/index sin modo da un error raro y hay que ver qué fuente
    concreta está fallando.

⚠️ Sin caché ni límite de peticiones — cada llamada repite todas las
consultas a APIs externas. Pensado para uso puntual/de validación, no
para tráfico real todavía (falta cache.py, sesión pendiente). Ninguno de
los dos modos tiene autenticación: quien tenga la URL puede usarlo.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pisocheck.geocoder import geocode
from pisocheck.main import analizar_direccion
from pisocheck.reports.html_report import render_html
from pisocheck.sources import catastro, opendata_vlc, osm

_ERROR_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>PisoCheck — error</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 60px auto; color: #0f172a;">
<h1>{titulo}</h1>
<p>{mensaje}</p>
<p style="color:#64748b; font-size:0.9rem;">
Ejemplo: <code>/api/index?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent</code><br>
Diagnóstico: <code>/api/index?modo=smoke</code>
</p>
<p><a href="?">← Volver al formulario</a></p>
</body></html>"""

# Página de inicio: se sirve cuando se visita la función sin parámetros.
# El <form method="GET" action=""> envía a la misma URL desde la que se
# sirvió esta página (funcione en "/" o en "/api/index"), así que no hay
# que acertar ninguna ruta a mano ni depender de que Vercel enrute un
# archivo estático aparte junto a la función.
_HOME_PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PisoCheck</title>
<style>
  :root { --bg:#f8fafc; --card:#ffffff; --border:#e2e8f0; --text:#0f172a; --muted:#64748b; --accent:#16a34a; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width: 560px; margin: 0 auto; padding: 60px 20px; }
  h1 { font-size: 1.8rem; margin: 0 0 6px; }
  p.tagline { color: var(--muted); margin: 0 0 32px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }
  label { display:block; font-size:0.85rem; font-weight:600; margin-bottom:6px; }
  input[type=text] {
    width:100%; padding:12px 14px; border:1px solid var(--border); border-radius:10px;
    font-size:1rem; margin-bottom:16px;
  }
  input[type=text]:focus { outline:2px solid var(--accent); border-color:var(--accent); }
  button {
    width:100%; padding:13px; border:none; border-radius:10px; background:var(--accent);
    color:white; font-size:1rem; font-weight:600; cursor:pointer;
  }
  button:hover { opacity:0.92; }
  .ejemplos { margin-top:18px; font-size:0.85rem; color:var(--muted); }
  .ejemplos a { color:var(--text); text-decoration:none; border-bottom:1px dotted var(--muted); }
  .aviso { margin-top:24px; font-size:0.8rem; color:var(--muted); }
  .aviso a { color:var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <h1>PisoCheck</h1>
  <p class="tagline">Análisis de zona para comprar o alquilar, con datos públicos.</p>
  <div class="card">
    <form method="GET" action="">
      <label for="direccion">Dirección</label>
      <input type="text" id="direccion" name="direccion" placeholder="Carrer del Garbí 24, Torrent" required>
      <label for="vs">Comparar con (opcional)</label>
      <input type="text" id="vs" name="vs" placeholder="Otra dirección">
      <button type="submit">Analizar</button>
    </form>
    <div class="ejemplos">
      Prueba con:
      <a href="?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent">Carrer del Garbí 24, Torrent</a> ·
      <a href="?direccion=Av.+de+Burjassot+71%2C+Valencia">Av. de Burjassot 71, Valencia</a>
    </div>
  </div>
  <p class="aviso">
    Tarda unos segundos (consulta varias fuentes públicas en directo).
    · <a href="?modo=smoke">Diagnóstico</a>
  </p>
</div>
</body>
</html>"""

# --- modo "analizar" -------------------------------------------------------


async def _analizar_html(direccion: str, direccion_vs: str | None) -> str:
    report = await analizar_direccion(direccion)
    comparacion = await analizar_direccion(direccion_vs) if direccion_vs else None
    return render_html(report, comparacion=comparacion)


# --- modo "smoke" (diagnóstico) --------------------------------------------

_CASOS_SMOKE = [
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


async def _probar_caso_smoke(caso: dict) -> dict:
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


async def _run_smoke() -> list[dict]:
    return [await _probar_caso_smoke(caso) for caso in _CASOS_SMOKE]


# --- routing -----------------------------------------------------------


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        modo = (query.get("modo") or [None])[0]

        if modo == "smoke":
            self._modo_smoke()
            return

        direccion = (query.get("direccion") or [None])[0]
        if not direccion:
            self._responder_html(200, _HOME_PAGE)
            return

        direccion_vs = (query.get("vs") or [None])[0]
        try:
            html_out = asyncio.run(_analizar_html(direccion, direccion_vs))
            self._responder_html(200, html_out)
        except Exception as e:  # noqa: BLE001 — cualquier fallo debe dar una página legible
            self._responder_html(
                502,
                _ERROR_PAGE.format(
                    titulo="No se pudo completar el análisis",
                    mensaje=f"{html.escape(type(e).__name__)}: {html.escape(str(e))}",
                ),
            )

    def _modo_smoke(self) -> None:
        try:
            resultados = asyncio.run(_run_smoke())
            body = json.dumps({"ok": True, "resultados": resultados}, ensure_ascii=False, indent=2)
            status = 200
        except Exception as e:  # noqa: BLE001
            body = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
            status = 500
        self._responder(status, body.encode("utf-8"), "application/json; charset=utf-8")

    def _responder_html(self, status: int, body_html: str) -> None:
        self._responder(status, body_html.encode("utf-8"), "text/html; charset=utf-8")

    def _responder(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)
