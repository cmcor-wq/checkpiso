from pisocheck.scoring.factors import (
    label_from_score,
    score_colegios,
    score_limpieza_zona,
    score_ocio_nocturno,
    score_quejas_vecinales,
    score_riesgo_inundacion,
    score_salud_farmacias,
    score_sol_orientacion,
    score_transporte,
    score_zona_verde,
)

# GARBI24_FIXTURE (spec §13): rangos esperados para los factores que ya
# tenemos fuente de datos.
GARBI24_ESPERADO = {
    "ocio_nocturno": (2.0, 4.0),
    "salud_farmacias": (8.0, 10.0),
    "transporte": (6.0, 8.0),
}


def test_ocio_nocturno_garbi24_dentro_de_rango_esperado():
    # Varios bares relativamente cerca, coherente con el centro de Torrent
    # donde está Garbí 24 (spec: puntuación esperada 2.0-4.0).
    establecimientos = [
        {"distancia_m": 50, "nombre": "Bar Central"},
        {"distancia_m": 90, "nombre": "Pub Nocturno"},
        {"distancia_m": 200, "nombre": "Terraza Plaza"},
    ]
    score, _, _ = score_ocio_nocturno(establecimientos)
    lo, hi = GARBI24_ESPERADO["ocio_nocturno"]
    assert lo <= score <= hi


def test_salud_farmacias_garbi24_dentro_de_rango_esperado():
    farmacias = [{"distancia_m": 150, "nombre": "Farmacia Garbí"}]
    score, _, _ = score_salud_farmacias(farmacias)
    lo, hi = GARBI24_ESPERADO["salud_farmacias"]
    assert lo <= score <= hi


def test_transporte_garbi24_dentro_de_rango_esperado():
    paradas = [{"tipo": "metro", "distancia_m": 650}, {"tipo": "bus", "distancia_m": 120}]
    score, _, _ = score_transporte(paradas)
    lo, hi = GARBI24_ESPERADO["transporte"]
    assert lo <= score <= hi


def test_ocio_nocturno_sin_locales_puntua_alto():
    score, desc, _ = score_ocio_nocturno([])
    assert score >= 9.0
    assert "Sin bares" in desc


def test_transporte_sin_metro_cercano_puntua_bajo():
    score, _, _ = score_transporte([{"tipo": "bus", "distancia_m": 100}])
    assert score == 2.0


def test_zona_verde_sin_parques_es_alerta():
    score, _, _ = score_zona_verde([])
    assert score < 4  # umbral de alerta, spec §8 FactorResult.alerta


def test_colegios_cercano_puntua_bien():
    score, _, _ = score_colegios([{"distancia_m": 200}])
    assert score >= 8.0


def test_quejas_vecinales_campanar_referencia():
    # 8 quejas en 12 meses, como en el CLI de ejemplo de la spec §11.
    score, desc, _ = score_quejas_vecinales(
        {"total": 8, "distrito": "CAMPANAR", "breakdown": {"ALUMBRADO": 2}}
    )
    assert 5.0 <= score <= 7.0
    assert "CAMPANAR" in desc


def test_limpieza_zona_muchas_quejas_de_basura_puntua_bajo():
    score, desc, _ = score_limpieza_zona(
        {"total": 20, "distrito": "CAMPANAR", "breakdown": {"RESIDUOS": 12, "LIMPIEZA VIA PUBLICA": 8}}
    )
    assert score < 4  # alerta
    assert "indicador indirecto" in desc


def test_limpieza_zona_sin_quejas_puntua_bien():
    score, _, _ = score_limpieza_zona({"total": 0, "distrito": "CAMPANAR", "breakdown": {}})
    assert score >= 8.0


def test_sol_orientacion_burjassot71_referencia():
    # spec CLI ejemplo: "Solar: 4.8h/día media anual [6.0/10]"
    score, _, _ = score_sol_orientacion({"horas_sol_dia": 4.8})
    assert score == 6.0


def test_riesgo_inundacion_zona_t10_es_critico():
    score, desc, _ = score_riesgo_inundacion({"zona_t10": True})
    assert score == 1.0
    assert "alta frecuencia" in desc


def test_riesgo_inundacion_sin_riesgo():
    score, _, _ = score_riesgo_inundacion({})
    assert score == 9.0


def test_label_from_score_umbrales():
    assert label_from_score(1.0) == "Crítico"
    assert label_from_score(4.0) == "Bajo"
    assert label_from_score(5.5) == "Moderado"
    assert label_from_score(7.0) == "Bueno"
    assert label_from_score(8.5) == "Excelente"
