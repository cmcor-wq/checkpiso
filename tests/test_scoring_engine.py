from pisocheck.models import AddressData
from pisocheck.scoring.engine import build_report


def _address() -> AddressData:
    return AddressData(raw="Test", lat=39.48, lng=-0.38, municipio="Valencia")


def test_build_report_omite_factores_sin_datos():
    raw_data = {
        "transporte": [{"tipo": "metro", "distancia_m": 200}],
        "zona_verde": None,  # explícitamente sin dato
        # el resto de factores ni se mencionan -> también se omiten
    }
    report = build_report(_address(), raw_data)

    factor_ids = {f.factor_id for f in report.factores}
    assert factor_ids == {"transporte"}
    assert report.get_factor("zona_verde") is None
    assert report.get_factor("riesgo_inundacion") is None


def test_build_report_score_global_es_media_de_disponibles():
    raw_data = {
        "transporte": [{"tipo": "metro", "distancia_m": 200}],  # 9.5
        "zona_verde": [],  # 1.0
    }
    report = build_report(_address(), raw_data)

    assert report.score_global == round((9.5 + 1.0) / 2, 2)


def test_build_report_detecta_alertas():
    raw_data = {
        "zona_verde": [],  # score 1.0 -> alerta
        "transporte": [{"tipo": "metro", "distancia_m": 200}],  # score 9.5 -> no alerta
    }
    report = build_report(_address(), raw_data)

    alerta_ids = {f.factor_id for f in report.alertas}
    assert alerta_ids == {"zona_verde"}


def test_build_report_sin_factores_score_global_cero():
    report = build_report(_address(), {})
    assert report.score_global == 0.0
    assert report.alertas == []
