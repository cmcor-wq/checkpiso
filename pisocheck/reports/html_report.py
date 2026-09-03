"""Informe HTML narrativo, autocontenido (sin CSS/JS externos).

Se puede abrir directamente en un navegador (file://) o servir tal cual —
no depende de red para renderizarse, a diferencia de las fuentes de datos.
"""

from __future__ import annotations

from pathlib import Path

import jinja2

from pisocheck.models import ReportData
from pisocheck.scoring.factors import FACTOR_NOMBRES

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "j2"]),
)

_ORDEN_FACTORES = list(FACTOR_NOMBRES.keys())


def _color_para_score(score: float) -> str:
    if score < 4:
        return "#dc2626"  # rojo — crítico
    if score < 5.5:
        return "#ea580c"  # naranja — bajo
    if score < 7:
        return "#ca8a04"  # ámbar — moderado
    if score < 8.5:
        return "#65a30d"  # verde lima — bueno
    return "#16a34a"  # verde — excelente


def _factores_ordenados(report: ReportData) -> list:
    return sorted(
        report.factores,
        key=lambda f: _ORDEN_FACTORES.index(f.factor_id)
        if f.factor_id in _ORDEN_FACTORES
        else len(_ORDEN_FACTORES),
    )


def render_html(report: ReportData, comparacion: ReportData | None = None) -> str:
    template = _env.get_template("informe.html.j2")
    fuentes = sorted({f.fuente for f in report.factores})
    factores_pendientes = [
        nombre
        for factor_id, nombre in FACTOR_NOMBRES.items()
        if report.get_factor(factor_id) is None
    ]

    return template.render(
        report=report,
        comparacion=comparacion,
        factores=_factores_ordenados(report),
        factores_comparacion=_factores_ordenados(comparacion) if comparacion else None,
        factor_nombres=FACTOR_NOMBRES,
        factores_pendientes=factores_pendientes,
        color_para_score=_color_para_score,
        fuentes=fuentes,
    )


def guardar_html(
    report: ReportData, output_path: Path, comparacion: ReportData | None = None
) -> Path:
    html = render_html(report, comparacion=comparacion)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
