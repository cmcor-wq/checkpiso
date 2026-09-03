"""Funciones de puntuación por factor (spec §4 y §9).

Cada `score_*` recibe los datos crudos que ya trajo el módulo de `sources`
correspondiente y devuelve `(score, descripcion, datos_adicionales)`. El
`label` ("Crítico"/"Bajo"/"Moderado"/"Bueno"/"Excelente") y la `fuente` se
derivan centralmente en `engine.py` a partir de `FACTOR_FUENTES` y
`label_from_score` — así cada función de scoring se queda solo con la
lógica de negocio.

⚠️ Simplificaciones conocidas por falta de fuente todavía integrada:
- `ocio_nocturno`, `iluminacion`, `colegios`, `aparcamiento`, `comercio` y
  `salud_farmacias` usan solo datos de OpenStreetMap (distancia/conteo).
  La spec original combina esto con Google Places (horario de cierre,
  "24h", etc.) — cuando haya API key de Places, estas funciones deberían
  enriquecerse con esos matices en vez de sustituirse.
- `iluminacion` no incluye NASA Black Marble todavía (Sesión 4).
- `ruido_nocturno` no usa un mapa de ruido oficial (Lnight, sin fuente
  pública accesible) — es un proxy: locales de ocio/restauración cercanos
  con horario de cierre tardío (según el tag OSM `opening_hours`, parseado
  con una heurística simple, no un parser completo de esa sintaxis).
- `limpieza_zona` no mide limpieza real (no existe esa fuente pública) — es
  un proxy inferido del volumen de quejas de "limpieza vía pública" y
  "residuos" en Open Data Valencia. Es una correlación razonable (mucha
  queja de basuras → probablemente recogida/reciclaje deficientes), no una
  medición directa. Igual que `quejas_vecinales`, solo cubre Valencia
  ciudad — Torrent se queda sin este factor hasta tener GIVP.
- Los umbrales de distancia/conteo son estimaciones razonables, no vienen
  de la spec (que solo da los extremos 0 y 10 de cada factor) — hay que
  contrastarlos con los dos pisos de referencia en cuanto haya datos reales.
"""

from __future__ import annotations


def label_from_score(score: float) -> str:
    if score < 4:
        return "Crítico"
    if score < 5.5:
        return "Bajo"
    if score < 7:
        return "Moderado"
    if score < 8.5:
        return "Bueno"
    return "Excelente"


# ---------------------------------------------------------------------------
# 1. Riesgo de inundación (spec §9, literal) — sin fuente integrada todavía.
# ---------------------------------------------------------------------------
def score_riesgo_inundacion(data: dict) -> tuple[float, str, dict]:
    if data.get("zona_t10"):
        score, motivo = 1.0, "en zona inundable de alta frecuencia (T10)"
    elif data.get("zona_t100"):
        score, motivo = 2.5, "en zona inundable T100"
    elif data.get("zona_t500"):
        score, motivo = 4.0, "en zona inundable T500 (riesgo bajo)"
    elif data.get("municipio_afectado_dana"):
        score, motivo = 3.5, "en un municipio afectado por la DANA de 2024"
    else:
        score, motivo = 9.0, "sin riesgo de inundación verificado"
    return score, f"La vivienda está {motivo}.", {}


# ---------------------------------------------------------------------------
# 2. Ocio nocturno — datos: pisocheck.sources.osm.ocio_nocturno()
# ---------------------------------------------------------------------------
def score_ocio_nocturno(establecimientos: list[dict]) -> tuple[float, str, dict]:
    penalty = 0.0
    cercanos = 0
    for est in establecimientos:
        d = est["distancia_m"]
        if d > 500:
            continue
        cercanos += 1
        penalty += 3.0 if d < 100 else 1.5 if d < 250 else 0.8
    score = max(1.0, round(10.0 - penalty, 1))
    desc = (
        f"{cercanos} bares/pubs en 500m."
        if cercanos
        else "Sin bares ni pubs en 500m."
    )
    return score, desc, {"establecimientos": establecimientos[:10]}


# ---------------------------------------------------------------------------
# 3. Ruido nocturno — proxy: osm.ocio_tardio() (sin mapa Lnight oficial).
# Distinto de `ocio_nocturno`: aquí también cuentan los restaurantes, y el
# peso depende de si el local cierra tarde (>=23:00), no solo de la
# distancia. `cierra_tarde=None` (horario no encontrado/no interpretable)
# penaliza menos que un cierre tardío confirmado, pero más que uno confirmado
# temprano — es duda razonable, no ausencia de riesgo.
# ---------------------------------------------------------------------------
def score_ruido_nocturno(establecimientos: list[dict]) -> tuple[float, str, dict]:
    penalty = 0.0
    cercanos = 0
    confirmados_tarde = 0
    for est in establecimientos:
        d = est["distancia_m"]
        if d > 300:
            continue
        cercanos += 1
        cierra_tarde = est.get("cierra_tarde")
        if cierra_tarde is True:
            confirmados_tarde += 1
            peso = 3.5 if d < 100 else 2.0
        elif cierra_tarde is None:
            peso = 1.5 if d < 100 else 0.8
        else:
            peso = 0.3
        penalty += peso
    score = max(1.0, round(10.0 - penalty, 1))
    if cercanos == 0:
        desc = "Sin bares, pubs ni restaurantes en 300m."
    else:
        desc = (
            f"{cercanos} locales de ocio/restauración en 300m, "
            f"{confirmados_tarde} confirmados con cierre después de las 23:00 "
            "(horario de OpenStreetMap, aproximado)."
        )
    return score, desc, {"establecimientos": establecimientos[:10]}


# ---------------------------------------------------------------------------
# 4. Transporte (spec §9, literal, "metro" incluye subway+light_rail de OSM)
# ---------------------------------------------------------------------------
def score_transporte(paradas: list[dict]) -> tuple[float, str, dict]:
    metro_mas_cercano = min(
        (p["distancia_m"] for p in paradas if p.get("tipo") == "metro"), default=9999
    )
    if metro_mas_cercano < 300:
        score = 9.5
    elif metro_mas_cercano < 500:
        score = 8.0
    elif metro_mas_cercano < 800:
        score = 6.5
    elif metro_mas_cercano < 1200:
        score = 5.0
    else:
        score = 2.0
    desc = (
        f"Parada de metro/tranvía a {metro_mas_cercano}m."
        if metro_mas_cercano < 9999
        else "Sin metro/tranvía en el radio consultado."
    )
    return score, desc, {"paradas": paradas[:10]}


# ---------------------------------------------------------------------------
# 4. Zona verde — datos: osm.zonas_verdes()
# ---------------------------------------------------------------------------
def score_zona_verde(parques: list[dict]) -> tuple[float, str, dict]:
    if not parques:
        return 1.0, "Sin parque ni zona verde en el radio consultado.", {}
    d = min(p["distancia_m"] for p in parques)
    if d < 300:
        score = 9.5
    elif d < 600:
        score = 7.5
    elif d < 1000:
        score = 5.5
    else:
        score = 3.0
    return score, f"Zona verde más cercana a {d}m.", {"parques": parques[:5]}


# ---------------------------------------------------------------------------
# 5. Iluminación — datos: osm.farolas() (parcial, sin NASA Black Marble)
# ---------------------------------------------------------------------------
def score_iluminacion(farolas: list[dict]) -> tuple[float, str, dict]:
    n = len(farolas)
    if n == 0:
        score = 2.0
    elif n < 5:
        score = 4.5
    elif n < 15:
        score = 6.5
    elif n < 30:
        score = 8.0
    else:
        score = 9.0
    return score, f"{n} farolas registradas en OSM en el radio consultado.", {}


# ---------------------------------------------------------------------------
# 6. Colegios — datos: osm.colegios()
# ---------------------------------------------------------------------------
def score_colegios(colegios: list[dict]) -> tuple[float, str, dict]:
    if not colegios:
        return 1.5, "Sin colegios en 1km.", {}
    d = min(c["distancia_m"] for c in colegios)
    if d < 500:
        score = 9.0
    elif d < 800:
        score = 7.0
    elif d < 1000:
        score = 5.0
    else:
        score = 3.0
    return score, f"Colegio más cercano a {d}m.", {"colegios": colegios[:5]}


# ---------------------------------------------------------------------------
# 7. Aparcamiento — datos: osm.parking()
# ---------------------------------------------------------------------------
def score_aparcamiento(parkings: list[dict]) -> tuple[float, str, dict]:
    if not parkings:
        return 2.0, "Sin aparcamiento en 800m.", {}
    d = min(p["distancia_m"] for p in parkings)
    if d < 300:
        score = 8.5
    elif d < 500:
        score = 7.0
    elif d < 800:
        score = 5.0
    else:
        score = 3.0
    return score, f"Aparcamiento más cercano a {d}m.", {"parkings": parkings[:5]}


# ---------------------------------------------------------------------------
# 8. Comercio — datos: osm.supermercados()
# ---------------------------------------------------------------------------
def score_comercio(supermercados: list[dict]) -> tuple[float, str, dict]:
    if not supermercados:
        return 1.5, "Sin supermercados en 1km.", {}
    d = min(s["distancia_m"] for s in supermercados)
    base = 9.0 if d < 500 else 7.0 if d < 800 else 5.0 if d < 1000 else 3.0
    score = min(10.0, base + min(1.0, (len(supermercados) - 1) * 0.2))
    return (
        round(score, 1),
        f"{len(supermercados)} supermercados en 1km, el más cercano a {d}m.",
        {"supermercados": supermercados[:5]},
    )


# ---------------------------------------------------------------------------
# 9. Salud y farmacias — datos: osm.farmacias()
# ---------------------------------------------------------------------------
def score_salud_farmacias(farmacias: list[dict]) -> tuple[float, str, dict]:
    if not farmacias:
        return 1.0, "Sin farmacias en 1km.", {}
    d = min(f["distancia_m"] for f in farmacias)
    if d < 400:
        score = 9.0
    elif d < 700:
        score = 7.0
    elif d < 1000:
        score = 5.0
    else:
        score = 3.0
    return score, f"Farmacia más cercana a {d}m.", {"farmacias": farmacias[:5]}


# ---------------------------------------------------------------------------
# 10. Quejas vecinales — datos: opendata_vlc.get_quejas() (solo Valencia ciudad)
# ---------------------------------------------------------------------------
def score_quejas_vecinales(quejas: dict) -> tuple[float, str, dict]:
    total = quejas["total"]
    if total == 0:
        score = 9.5
    elif total <= 5:
        score = 8.0
    elif total <= 15:
        score = 6.0
    elif total <= 30:
        score = 4.0
    elif total <= 50:
        score = 2.5
    else:
        score = 1.0
    distrito = quejas.get("distrito", "el distrito")
    descripcion = f"{total} quejas/sugerencias en {distrito} en los últimos 12 meses."
    return (score, descripcion, {"breakdown": quejas.get("breakdown", {})})


# ---------------------------------------------------------------------------
# 12. Limpieza de zona — proxy: opendata_vlc.get_quejas(materias=MATERIAS_LIMPIEZA)
# (solo Valencia ciudad). No medimos limpieza directamente (no hay fuente
# pública de eso) — usamos el volumen de quejas de "limpieza vía pública" y
# "residuos" como indicador indirecto: si hay muchas, es razonable asumir
# que la recogida/reciclaje no está funcionando bien en la zona. Es una
# inferencia, no una medición, y debería quedar claro en el informe.
# ---------------------------------------------------------------------------
def score_limpieza_zona(quejas_limpieza: dict) -> tuple[float, str, dict]:
    total = quejas_limpieza["total"]
    if total == 0:
        score = 9.0
    elif total <= 3:
        score = 7.0
    elif total <= 8:
        score = 5.0
    elif total <= 15:
        score = 3.0
    else:
        score = 1.5
    distrito = quejas_limpieza.get("distrito", "el distrito")
    descripcion = (
        f"{total} quejas de limpieza viaria/residuos en {distrito} en los últimos 12 "
        "meses. Es un indicador indirecto (no una medición de limpieza real): un "
        "volumen alto sugiere que la recogida o el reciclaje no funcionan bien en la zona."
    )
    return (score, descripcion, {"breakdown": quejas_limpieza.get("breakdown", {})})


# ---------------------------------------------------------------------------
# 13. Sol y orientación — datos: sources.solar.get_solar_data()
# ---------------------------------------------------------------------------
def score_sol_orientacion(solar_data: dict) -> tuple[float, str, dict]:
    horas = solar_data["horas_sol_dia"]
    if horas < 3:
        score = 2.0
    elif horas < 4:
        score = 4.0
    elif horas < 5:
        score = 6.0
    elif horas < 6:
        score = 8.0
    else:
        score = 9.5
    return (
        score,
        f"{horas} horas de sol equivalentes al día de media anual (PVGIS, orientación sur asumida).",
        {"horas_sol_mensual": solar_data.get("horas_sol_mensual", [])},
    )


FACTOR_NOMBRES: dict[str, str] = {
    "riesgo_inundacion": "Riesgo de inundación",
    "ocio_nocturno": "Ocio nocturno",
    "ruido_nocturno": "Ruido nocturno",
    "ruido_aereo": "Ruido aeronáutico",
    "transporte": "Transporte",
    "zona_verde": "Zona verde",
    "iluminacion": "Iluminación",
    "colegios": "Colegios",
    "aparcamiento": "Aparcamiento",
    "comercio": "Comercio",
    "salud_farmacias": "Salud y farmacias",
    "quejas_vecinales": "Quejas vecinales",
    "limpieza_zona": "Limpieza de zona",
    "sol_orientacion": "Sol y orientación",
}

FACTOR_FUENTES: dict[str, str] = {
    "riesgo_inundacion": "SNCZI + CHJ",
    "ocio_nocturno": "OpenStreetMap (Overpass)",
    "ruido_nocturno": "OpenStreetMap (Overpass) — proxy: locales que cierran tarde, sin mapa Lnight oficial",
    "transporte": "OpenStreetMap (Overpass)",
    "zona_verde": "OpenStreetMap (Overpass)",
    "iluminacion": "OpenStreetMap (Overpass) — parcial, sin NASA Black Marble",
    "colegios": "OpenStreetMap (Overpass)",
    "aparcamiento": "OpenStreetMap (Overpass)",
    "comercio": "OpenStreetMap (Overpass)",
    "salud_farmacias": "OpenStreetMap (Overpass)",
    "quejas_vecinales": "Open Data Valencia",
    "limpieza_zona": "Open Data Valencia (proxy: quejas de limpieza/residuos)",
    "sol_orientacion": "PVGIS · EU JRC",
}

FACTOR_SCORERS = {
    "riesgo_inundacion": score_riesgo_inundacion,
    "ocio_nocturno": score_ocio_nocturno,
    "ruido_nocturno": score_ruido_nocturno,
    "transporte": score_transporte,
    "zona_verde": score_zona_verde,
    "iluminacion": score_iluminacion,
    "colegios": score_colegios,
    "aparcamiento": score_aparcamiento,
    "comercio": score_comercio,
    "salud_farmacias": score_salud_farmacias,
    "quejas_vecinales": score_quejas_vecinales,
    "limpieza_zona": score_limpieza_zona,
    "sol_orientacion": score_sol_orientacion,
}
