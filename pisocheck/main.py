"""CLI de PisoCheck (spec §11, sin generación de PDF por ahora).

Flujo (spec §7): dirección en texto libre -> geocoder -> catastro ->
fuentes en paralelo -> scoring/engine -> informe HTML.

Cada fuente que falla (red, parseo, o simplemente no aplica — p. ej. Open
Data Valencia solo cubre Valencia ciudad) se omite en vez de romper todo
el análisis; el informe final solo promedia los factores disponibles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from pisocheck import config
from pisocheck.address_parsing import extraer_calle_numero
from pisocheck.geocoder import GeocodeError, geocode
from pisocheck.models import AddressData, ReportData
from pisocheck.reports import html_report
from pisocheck.scoring import engine
from pisocheck.sources import catastro, opendata_vlc, osm, solar
from pisocheck.sources.catastro import CatastroError
from pisocheck.utils import quitar_acentos, slugify


async def _safe(coro, *, verbose: bool, nombre: str):
    try:
        resultado = await coro
    except Exception as e:  # noqa: BLE001 — cualquier fallo de una fuente no debe tumbar el resto
        if verbose:
            click.echo(f"… {nombre} no disponible ({type(e).__name__}: {e})")
        return None
    if verbose:
        click.echo(f"✓ {nombre}")
    return resultado


async def _enriquecer_con_catastro(
    address: AddressData, raw_address: str, *, verbose: bool
) -> AddressData:
    calle, numero = extraer_calle_numero(raw_address)
    if not (calle and numero and address.provincia):
        if verbose:
            click.echo("… Catastro omitido (no se pudo determinar calle/número/provincia)")
        return address

    try:
        data = await catastro.consulta_dnp(
            quitar_acentos(address.provincia).upper(),
            quitar_acentos(address.municipio).upper(),
            calle,
            numero,
        )
    except CatastroError as e:
        if verbose:
            click.echo(f"… Catastro sin datos ({e})")
        return address

    if verbose:
        click.echo(
            f"✓ Catastro: ref. {data.get('ref_catastral')} · "
            f"{data.get('superficie_construida')}m² · {data.get('anio_construccion')}"
        )
    return catastro.merge_into_address(address, data)


async def _recolectar_fuentes(address: AddressData, *, verbose: bool) -> dict:
    lat, lng = address.lat, address.lng

    tareas = {
        "ocio_nocturno": _safe(osm.ocio_nocturno(lat, lng), verbose=verbose, nombre="OSM ocio nocturno"),
        "ruido_nocturno": _safe(osm.ocio_tardio(lat, lng), verbose=verbose, nombre="OSM ruido nocturno"),
        "transporte": _safe(osm.transporte(lat, lng), verbose=verbose, nombre="OSM transporte"),
        "zona_verde": _safe(osm.zonas_verdes(lat, lng), verbose=verbose, nombre="OSM zonas verdes"),
        "iluminacion": _safe(osm.farolas(lat, lng), verbose=verbose, nombre="OSM farolas"),
        "colegios": _safe(osm.colegios(lat, lng), verbose=verbose, nombre="OSM colegios"),
        "aparcamiento": _safe(osm.parking(lat, lng), verbose=verbose, nombre="OSM aparcamiento"),
        "comercio": _safe(osm.supermercados(lat, lng), verbose=verbose, nombre="OSM comercio"),
        "salud_farmacias": _safe(osm.farmacias(lat, lng), verbose=verbose, nombre="OSM farmacias"),
        "sol_orientacion": _safe(solar.get_solar_data(lat, lng), verbose=verbose, nombre="PVGIS solar"),
    }

    es_valencia_ciudad = quitar_acentos(address.municipio or "").strip().lower() == "valencia"
    if es_valencia_ciudad and address.distrito:
        tareas["quejas_vecinales"] = _safe(
            opendata_vlc.get_quejas(address.distrito), verbose=verbose, nombre="Open Data VLC quejas"
        )
        tareas["limpieza_zona"] = _safe(
            opendata_vlc.get_quejas(address.distrito, materias=opendata_vlc.MATERIAS_LIMPIEZA),
            verbose=verbose,
            nombre="Open Data VLC limpieza",
        )
    elif verbose:
        click.echo("… Quejas vecinales / limpieza omitidas (solo cubierto para Valencia ciudad)")

    claves = list(tareas.keys())
    resultados = await asyncio.gather(*tareas.values())
    return dict(zip(claves, resultados, strict=True))


async def analizar_direccion(raw_address: str, *, verbose: bool = False) -> ReportData:
    try:
        address = await geocode(raw_address)
    except GeocodeError as e:
        raise click.ClickException(f"No se pudo geocodificar {raw_address!r}: {e}") from e

    if verbose:
        click.echo(
            f"✓ Geocodificado: {address.lat}, {address.lng} · {address.municipio} · "
            f"distrito={address.distrito!r} barrio={address.barrio!r}"
        )

    address = await _enriquecer_con_catastro(address, raw_address, verbose=verbose)
    raw_data = await _recolectar_fuentes(address, verbose=verbose)
    return engine.build_report(address, raw_data)


async def _run(direccion: str, direccion_vs: str | None, output_dir: Path, verbose: bool) -> None:
    report = await analizar_direccion(direccion, verbose=verbose)

    comparacion = None
    if direccion_vs:
        if verbose:
            click.echo(f"\n--- Comparando con: {direccion_vs} ---")
        comparacion = await analizar_direccion(direccion_vs, verbose=verbose)

    output_path = Path(output_dir) / f"pisocheck-{slugify(direccion)}-informe.html"
    html_report.guardar_html(report, output_path, comparacion=comparacion)

    click.echo("━" * 42)
    click.echo(f"Puntuación global: {report.score_global:.1f} / 10")
    if report.alertas:
        nombres_alerta = ", ".join(f.factor_id for f in report.alertas)
        click.echo(f"Alertas ({len(report.alertas)}): {nombres_alerta}")
    if comparacion:
        click.echo(f"Comparativa — {direccion_vs}: {comparacion.score_global:.1f} / 10")
    click.echo(f"Informe generado: {output_path}")


@click.command()
@click.argument("direccion")
@click.option("--vs", "direccion_vs", default=None, help="Comparar con una segunda dirección.")
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directorio de salida (por defecto: OUTPUT_DIR de .env, o ./informes).",
)
@click.option("--verbose", is_flag=True, help="Muestra cada llamada a fuente de datos.")
def main(direccion: str, direccion_vs: str | None, output_dir: Path | None, verbose: bool) -> None:
    """Analiza DIRECCION y genera un informe HTML de la zona."""
    asyncio.run(_run(direccion, direccion_vs, output_dir or config.OUTPUT_DIR, verbose))


if __name__ == "__main__":
    main()
