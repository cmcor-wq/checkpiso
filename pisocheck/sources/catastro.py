"""Sede Electrónica del Catastro — servicio OVC Consulta_DNPPP.

⚠️ Sin acceso de red en este entorno no ha sido posible validar el XML de
respuesta contra el servicio real. El parser está escrito de forma
namespace-agnostic y tolerante a campos ausentes, basado en el esquema
documentado de Catastro (elementos <bico><bi><idbi><rc>, <dt>, <debi>), pero
debe verificarse con una llamada real antes de confiar en él en producción
(hay un test con fixture en tests/test_catastro.py que documenta la forma
exacta que se está asumiendo — si el XML real difiere, ese es el primer
sitio a corregir).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

import httpx

from pisocheck.config import DEFAULT_USER_AGENT, HTTP_TIMEOUT_SECONDS
from pisocheck.models import AddressData

CATASTRO_URL = (
    "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPPP"
)


class CatastroError(RuntimeError):
    """El Catastro no devolvió datos utilizables para esta dirección."""


def _local(tag: str) -> str:
    """Quita el namespace de un tag XML: '{ns}rc' -> 'rc'."""
    return tag.rsplit("}", 1)[-1]


def _find(elem: ET.Element | None, *path: str) -> ET.Element | None:
    """Busca descendiendo por nombres de tag ignorando namespaces."""
    if elem is None:
        return None
    current = elem
    for name in path:
        nxt = None
        for child in current:
            if _local(child.tag) == name:
                nxt = child
                break
        if nxt is None:
            return None
        current = nxt
    return current


def _text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    text = elem.text.strip()
    return text or None


def _parse_dnp_xml(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)

    control = _find(root, "control")
    if control is not None:
        err_text = _text(_find(control, "cuerr"))
        if err_text and err_text != "0":
            desc = _text(_find(root, "lerr", "err", "des")) or "Catastro devolvió error"
            raise CatastroError(desc)

    bi = _find(root, "bico", "bi")
    if bi is None:
        raise CatastroError("Respuesta de Catastro sin datos de bien inmueble (<bi>)")

    rc = _find(bi, "idbi", "rc")
    ref_catastral = None
    if rc is not None:
        parts = [
            _text(_find(rc, "pc1")) or "",
            _text(_find(rc, "pc2")) or "",
            _text(_find(rc, "car")) or "",
            _text(_find(rc, "cc1")) or "",
            _text(_find(rc, "cc2")) or "",
        ]
        joined = "".join(parts)
        ref_catastral = joined or None

    debi = _find(bi, "debi")
    superficie = _text(_find(debi, "sfc")) if debi is not None else None
    anio = _text(_find(debi, "ant")) if debi is not None else None
    uso = _text(_find(debi, "luso")) if debi is not None else None

    direccion_catastral = _text(_find(bi, "ldt"))

    return {
        "ref_catastral": ref_catastral,
        "superficie_construida": float(superficie) if superficie else None,
        "anio_construccion": int(anio) if anio else None,
        "uso": uso,
        "direccion_catastral": direccion_catastral,
    }


async def consulta_dnp(
    provincia: str,
    municipio: str,
    calle: str,
    numero: str,
    *,
    sigla: str = "CL",
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Consulta datos catastrales no protegidos de una parcela.

    Devuelve un dict con ref_catastral / superficie_construida /
    anio_construccion / uso / direccion_catastral (cualquiera puede ser
    None si el Catastro no lo aporta).
    """
    params = {
        "Provincia": provincia.upper(),
        "Municipio": municipio.upper(),
        "Sigla": sigla.upper(),
        "Calle": calle.upper(),
        "Numero": numero,
        "TipoConsulta": "PARCELA",
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        resp = await client.get(
            CATASTRO_URL, params=params, headers={"User-Agent": DEFAULT_USER_AGENT}
        )
        resp.raise_for_status()
    finally:
        if owns_client:
            await client.aclose()

    return _parse_dnp_xml(resp.content)


def merge_into_address(address: AddressData, catastro_data: dict) -> AddressData:
    """Devuelve una copia de AddressData con los campos catastrales rellenos."""
    updates = {
        k: v
        for k, v in {
            "ref_catastral": catastro_data.get("ref_catastral"),
            "superficie_construida": catastro_data.get("superficie_construida"),
            "anio_construccion": catastro_data.get("anio_construccion"),
        }.items()
        if v is not None
    }
    return replace(address, **updates)
