from pisocheck.models import AddressData, FactorResult, ReportData
from pisocheck.reports.html_report import render_html


def _report() -> ReportData:
    address = AddressData(
        raw="Carrer del Garbí 24, 2, Torrent",
        lat=39.4332,
        lng=-0.4680,
        municipio="Torrent",
        ref_catastral="8081706YJ1688S0003FU",
        superficie_construida=152,
        anio_construccion=1980,
    )
    factores = [
        FactorResult(
            factor_id="transporte",
            score=8.0,
            label="Bueno",
            valor_raw=[],
            descripcion="Parada de metro a 400m.",
            fuente="OpenStreetMap (Overpass)",
        ),
        FactorResult(
            factor_id="zona_verde",
            score=1.0,
            label="Crítico",
            valor_raw=[],
            descripcion="Sin parque ni zona verde en el radio consultado.",
            fuente="OpenStreetMap (Overpass)",
        ),
    ]
    return ReportData(address=address, factores=factores)


def test_render_html_incluye_datos_clave():
    html = render_html(_report())

    assert "Carrer del Garbí 24, 2, Torrent" in html
    assert "8081706YJ1688S0003FU" in html
    assert "Transporte" in html  # FACTOR_NOMBRES
    assert "4.5" in html  # score_global = (8.0+1.0)/2


def test_render_html_muestra_alertas():
    html = render_html(_report())
    idx_alertas = html.index("Alertas")
    idx_zona_verde = html.index("Sin parque ni zona verde")
    assert idx_alertas < idx_zona_verde


def test_render_html_lista_factores_pendientes():
    html = render_html(_report())
    # Con solo 2 de 14 factores, el resto debe listarse como pendientes.
    assert "Sin datos todavía para" in html
    assert "Riesgo de inundación" in html


def test_render_html_con_comparacion():
    report_a = _report()
    report_b = _report()
    report_b.address.raw = "Av. de Burjassot 71, Valencia"

    html = render_html(report_a, comparacion=report_b)

    assert "Comparativa" in html
    assert "Av. de Burjassot 71, Valencia" in html
