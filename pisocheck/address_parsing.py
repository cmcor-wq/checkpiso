"""Extrae calle/número del texto libre que escribe el usuario.

Necesario porque Catastro (`sources/catastro.py`) exige Calle+Numero como
parámetros exactos, y AddressData (spec §8) no los guarda — el geocoder
solo da lat/lng/municipio. En vez de fiarnos del campo "road" de Nominatim
(que puede venir en valenciano/catalán o con grafía distinta a la oficial
de Catastro), parseamos directamente lo que escribió el usuario, que es lo
que se usa en los dos ejemplos de referencia de la spec.

⚠️ Best-effort: funciona con el patrón típico español "<vía> <número>[,
resto]" y con los dos ejemplos de referencia (Garbí 24, Burjassot 71), pero
no es un parser robusto de direcciones — direcciones con número compuesto
("24 bis"), sin número, o con el número antes de la vía no se resolverán
bien.
"""

from __future__ import annotations

import re

from pisocheck.utils import quitar_acentos

_PREFIJOS_VIA = re.compile(
    r"^(carrer|calle|c/|avinguda|avenida|av\.?|plaza|pla[cç]a|paseo|passeig|camino|cam[ií])"
    r"\s+(del|de la|de l'|de|d')?\s*",
    re.IGNORECASE,
)

_CALLE_NUMERO_RE = re.compile(r"(.+?)\s+(\d+)\s*$")


def extraer_calle_numero(raw_address: str) -> tuple[str, str] | tuple[None, None]:
    """'Carrer del Garbí 24, 2, Torrent' -> ('GARBI', '24')."""
    primer_segmento = raw_address.split(",")[0].strip()
    match = _CALLE_NUMERO_RE.search(primer_segmento)
    if not match:
        return None, None

    calle_raw, numero = match.group(1), match.group(2)
    calle_sin_prefijo = _PREFIJOS_VIA.sub("", calle_raw).strip()
    if not calle_sin_prefijo:
        return None, None

    return quitar_acentos(calle_sin_prefijo).upper(), numero
