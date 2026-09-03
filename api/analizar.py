"""Endpoint Vercel: el análisis real de PisoCheck, servido como página web.

GET /api/analizar?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent
GET /api/analizar?direccion=...&vs=Otra+direccion   (comparativa)

A diferencia de api/smoke.py (que solo valida las fuentes), este endpoint
ejecuta el pipeline completo (pisocheck.main.analizar_direccion +
reports.html_report) y devuelve el informe HTML tal cual, para verlo
directamente en el navegador. Como Vercel sí tiene salida a internet real
(a diferencia del sandbox donde se escribió el resto del proyecto), esto
sirve tanto para validar las fuentes en condiciones reales como para usar
la herramienta de verdad sin instalar nada en local.

⚠️ Sin caché ni límite de peticiones — cada llamada repite todas las
consultas a APIs externas. Pensado para uso puntual/de validación, no
para tráfico real todavía (falta cache.py, sesión pendiente).
"""

from __future__ import annotations

import asyncio
import html
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pisocheck.main import analizar_direccion
from pisocheck.reports.html_report import render_html

_ERROR_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>PisoCheck — error</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 60px auto; color: #0f172a;">
<h1>{titulo}</h1>
<p>{mensaje}</p>
<p style="color:#64748b; font-size:0.9rem;">Ejemplo: <code>/api/analizar?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent</code></p>
</body></html>"""


async def _analizar(direccion: str, direccion_vs: str | None) -> str:
    report = await analizar_direccion(direccion)
    comparacion = await analizar_direccion(direccion_vs) if direccion_vs else None
    return render_html(report, comparacion=comparacion)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        direccion = (query.get("direccion") or [None])[0]
        direccion_vs = (query.get("vs") or [None])[0]

        if not direccion:
            self._responder(
                400,
                _ERROR_PAGE.format(
                    titulo="Falta el parámetro 'direccion'",
                    mensaje="Añade ?direccion=... a la URL con la dirección a analizar.",
                ),
            )
            return

        try:
            html_out = asyncio.run(_analizar(direccion, direccion_vs))
            self._responder(200, html_out)
        except Exception as e:  # noqa: BLE001 — cualquier fallo debe dar una página legible, no un 500 en blanco
            self._responder(
                502,
                _ERROR_PAGE.format(
                    titulo="No se pudo completar el análisis",
                    mensaje=f"{html.escape(type(e).__name__)}: {html.escape(str(e))}",
                ),
            )

    def _responder(self, status: int, body_html: str) -> None:
        body = body_html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
