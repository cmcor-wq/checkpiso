"""api/index.py vive fuera del paquete pisocheck (es el entrypoint de
Vercel), así que se carga por ruta de archivo en vez de por import normal.
Solo se comprueba el contenido estático (formulario, textos) — la lógica
de análisis en sí ya está probada via pisocheck.main / html_report.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "api_index", Path(__file__).parent.parent / "api" / "index.py"
)
api_index = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(api_index)


def test_home_page_tiene_formulario_con_get():
    html = api_index._HOME_PAGE
    assert '<form method="GET" action="">' in html
    assert 'name="direccion"' in html
    assert 'name="vs"' in html


def test_home_page_incluye_ejemplos_de_referencia():
    html = api_index._HOME_PAGE
    assert "Garb%C3%AD+24" in html  # Garbí 24 URL-encoded
    assert "Burjassot+71" in html


def test_error_page_formatea_sin_excepciones():
    html = api_index._ERROR_PAGE.format(titulo="Título", mensaje="Mensaje de prueba")
    assert "Título" in html
    assert "Mensaje de prueba" in html
