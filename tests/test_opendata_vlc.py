from pisocheck.sources.opendata_vlc import MATERIAS_RUIDO, get_quejas

# 8 quejas en Campanar en los últimos 12 meses, tal como aparece en el
# ejemplo de salida del CLI objetivo (spec §11).
CAMPANAR_RECORDS = {
    "total_count": 8,
    "results": [
        {"distrito": "CAMPANAR", "materia": "ALUMBRADO", "fecha_alta": "2025-09-01"},
        {"distrito": "CAMPANAR", "materia": "ALUMBRADO", "fecha_alta": "2025-10-12"},
        {"distrito": "CAMPANAR", "materia": "LIMPIEZA VIA PUBLICA", "fecha_alta": "2025-11-03"},
        {"distrito": "CAMPANAR", "materia": "LIMPIEZA VIA PUBLICA", "fecha_alta": "2025-12-01"},
        {"distrito": "CAMPANAR", "materia": "LIMPIEZA VIA PUBLICA", "fecha_alta": "2026-01-15"},
        {"distrito": "CAMPANAR", "materia": "RUIDO", "fecha_alta": "2026-02-20"},
        {"distrito": "CAMPANAR", "materia": "RUIDO", "fecha_alta": "2026-03-05"},
        {"distrito": "CAMPANAR", "materia": "RESIDUOS", "fecha_alta": "2026-04-01"},
    ],
}


async def test_get_quejas_campanar(httpx_mock):
    httpx_mock.add_response(method="GET", json=CAMPANAR_RECORDS)

    result = await get_quejas("Campanar")

    assert result["total"] == 8
    assert result["breakdown"]["ALUMBRADO"] == 2
    assert result["breakdown"]["RUIDO"] == 2
    assert result["distrito"] == "CAMPANAR"


async def test_get_quejas_filtra_por_materia(httpx_mock):
    ruido_only = {
        "total_count": 2,
        "results": [r for r in CAMPANAR_RECORDS["results"] if r["materia"] == "RUIDO"],
    }
    httpx_mock.add_response(method="GET", json=ruido_only)

    result = await get_quejas("Campanar", materias=MATERIAS_RUIDO)

    assert result["total"] == 2
    assert result["breakdown"] == {"RUIDO": 2}
