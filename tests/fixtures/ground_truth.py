"""Ground truth de los dos pisos ya analizados manualmente (spec §2 y §13).

Estos valores son los que deben reproducir los tests de cada fuente cuando
se les da una respuesta HTTP simulada con forma realista.
"""

GARBI24 = {
    "raw": "Carrer del Garbí 24, 2, Torrent",
    "lat": 39.4332,
    "lng": -0.4680,
    "municipio": "Torrent",
    "barrio": "Centro Torrent",
    "ref_catastral": "8081706YJ1688S0003FU",
    "superficie_construida": 152,
    "superficie_habitable": 142,
    "anio_construccion": 1980,
    "score_global_esperado": {"min": 4.5, "max": 5.8},
}

BURJASSOT71 = {
    "raw": "Av. de Burjassot 71, puerta 22, Valencia",
    "lat": 39.4866,
    "lng": -0.3877,
    "municipio": "Valencia",
    "distrito": "Campanar",
    "barrio": "Les Tendetes",
    "ref_catastral": "4742904YJ2744B",
    "superficie_habitable": 70,
    "anio_construccion": 1975,
    "score_global_esperado": 7.2,
}
