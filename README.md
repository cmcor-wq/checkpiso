# PisoCheck

Análisis automatizado de viviendas con datos públicos españoles. Dada una
dirección, cruza catastro, urbanismo, transporte, ocio, quejas vecinales,
zonas verdes, etc. y genera una puntuación de zona explicada de forma
narrativa. Ver la especificación completa en el documento original del
proyecto.

## Estado — Sesiones 1, 2 y 3 completadas

**Sesión 1** — fuentes de datos base:
- `pisocheck/models.py` — `AddressData`, `FactorResult`, `ReportData`.
- `pisocheck/geocoder.py` — dirección → lat/lng/municipio/distrito/barrio (Nominatim).
- `pisocheck/sources/catastro.py` — Consulta_DNPPP (Sede Catastro OVC, sin auth).
- `pisocheck/sources/opendata_vlc.py` — quejas/sugerencias por distrito (solo Valencia ciudad).
- `pisocheck/sources/osm.py` — Overpass: farolas, ocio nocturno, transporte, colegios, farmacias, supermercados, parques, parking.

**Sesión 2** — motor de puntuación:
- `pisocheck/scoring/factors.py` — funciones `score_*` para 13 de los 14 factores (ver tabla abajo).
- `pisocheck/scoring/engine.py` — `build_report(address, raw_data)`: arma el `ReportData` con los factores disponibles, omite los que faltan (no rompe la media).
- `pisocheck/sources/solar.py` — PVGIS real (horas de sol equivalentes/día).
- `pisocheck/sources/places.py` — Google Places Nearby Search, con degradación graceful (`None`) si no hay `GOOGLE_PLACES_API_KEY`.
- `pisocheck/sources/osm.py::ocio_tardio` — bares/pubs/restaurantes con `cierra_tarde` (True/False/None) inferido del tag OSM `opening_hours`, usado como proxy de ruido nocturno.

**Sesión 3** — CLI y generación de informe (sin PDF, no hacía falta):
- `pisocheck/main.py` — orquestación completa: geocoder → catastro → todas las fuentes en paralelo (`asyncio.gather`) → `scoring.engine` → HTML. Cada fuente que falla se omite sin tumbar el análisis. Comando: `pisocheck "Carrer del Garbí 24, 2, Torrent"` (o `python -m pisocheck.main "..."`).
- `pisocheck/address_parsing.py` — extrae calle/número del texto libre para poder llamar a Catastro automáticamente (probado exacto contra Garbí 24 y Burjassot 71).
- `pisocheck/reports/html_report.py` + `templates/informe.html.j2` — informe HTML autocontenido (sin CSS/JS externos, se abre directo en el navegador): puntuación global, alertas, catastro, grid de factores con barras, comparativa opcional (`--vs`), factores pendientes listados aparte.

54 tests con `pytest-httpx` (mocks), incluyendo un test de integración que
corre el pipeline completo de principio a fin. Ground truth: los datos
reales de Garbí 24 y Av. Burjassot 71.

### Cobertura de los 14 factores ahora mismo

| Factor | Estado |
|---|---|
| Ocio nocturno, Transporte, Zona verde, Iluminación, Colegios, Aparcamiento, Comercio, Salud/farmacias | ✅ Fuente OSM + scoring (parcial: sin el matiz de horario/24h que daría Places) |
| Ruido nocturno | ✅ Proxy: locales de ocio/restauración cercanos con cierre tras las 23:00 (heurística sobre `opening_hours` de OSM, no un mapa de ruido oficial) |
| Quejas vecinales | ✅ Solo Valencia ciudad (Open Data VLC); Torrent sin fuente (GIVP no implementado) |
| Limpieza zona | ✅ Proxy (no medición directa): volumen de quejas de limpieza/residuos en Open Data VLC — solo Valencia ciudad |
| Sol y orientación | ✅ PVGIS, orientación sur asumida por defecto |
| Riesgo inundación | ⚠️ Scoring listo, sin fuente (`sources/inundacion.py`, SNCZI — sesión 4) |
| Ruido aeronáutico | ❌ Sin fuente ni scoring todavía (sesión 4, ver riesgos abajo) |

Pendiente: PDF (fuera de alcance por ahora, no se necesita), cache SQLite
(cada análisis vuelve a llamar a todas las fuentes), SNCZI/inundación,
NASA Black Marble, ruido aeronáutico, mercado inmobiliario.

## ⚠️ Limitación conocida de este entorno

Este proyecto se ha desarrollado en un sandbox de Claude Code cuya política
de red **bloquea la salida a todos los dominios que usa PisoCheck**
(nominatim.openstreetmap.org, ovc.catastro.meh.es, overpass-api.de,
valencia.opendatasoft.com, idealista.com...) — solo permite PyPI, npm,
GitHub, etc. Por eso:

- Los tests usan respuestas HTTP **mockeadas** con forma fiel a la
  documentación de cada API (esto ya estaba en el diseño original, §13 de
  la spec — no es un parche por la limitación de red).
- El parseo de XML de Catastro y el mapeo de campos de Nominatim/Overpass
  están escritos según la documentación pública pero **no se han podido
  validar contra una llamada real** desde aquí. Cada módulo con este riesgo
  lo indica en su docstring.
- **Antes de confiar en esto en producción, hay que ejecutarlo una vez con
  red real** (tu máquina, o un entorno de Claude Code con política de red
  abierta) contra las dos direcciones de referencia y comparar con el
  ground truth de `tests/fixtures/ground_truth.py`.

## Decisiones tomadas en esta sesión

1. **Precio de mercado**: no se hará scraping de Idealista (riesgo legal —
   han demandado a scrapers en España). Se dejará para una fuente
   oficial/manual (INE, Ministerio de Vivienda, o entrada manual del precio
   de referencia del barrio) cuando se aborde ese factor.
2. **Google Places API / NASA EarthData**: sin claves todavía. La
   arquitectura ya está pensada para que estos factores degraden a "no
   disponible" en vez de romper el análisis; se integrarán cuando haya claves.
3. **`givp_scraper.py` / `pdf_report.py`**: los "prototipos funcionales"
   mencionados en la spec no existían en este repo ni los tenía el usuario
   a mano — se reconstruyen desde cero siguiendo la spec cuando toque
   (sesiones 3-4), no se asume código previo real.
4. Se quitó `asyncio` de las dependencias del `pyproject.toml` original (es
   de la librería estándar, no un paquete instalable) y se dejó `pydantic`
   fuera por ahora — los modelos siguen literalmente los `@dataclass` de la
   spec §8; se puede añadir pydantic más adelante si se necesita validación
   de inputs de CLI.

## Riesgos / huecos pendientes de decidir (no bloquean el código ya escrito)

- **AENA Webtrak**: sin API pública, requeriría scraping con
  Playwright/Puppeteer de una app JS interactiva — frágil y de legalidad
  dudosa según ToS. Alternativa: aproximar ruido aéreo con las
  servidumbres aeronáuticas publicadas (shapefiles oficiales) en vez de
  scraping en vivo.
- **NASA Black Marble**: necesita cuenta EarthData + token, y procesar
  HDF5 (deps no listadas todavía: `h5py` o `rasterio`).
- **OCOVAL / DOGV cartografía DANA**: sin API, solo formulario web o
  descarga manual de shapefiles — no automatizable sin intervención manual
  o convenio.
- **Cobertura geográfica real**: tal como está diseñado, el proyecto solo
  tiene fuentes completas para Valencia ciudad (quejas Open Data) y Torrent
  (GIVP, sin API real). Para otros municipios españoles, esos dos factores
  quedarían sin dato — a decidir si eso es aceptable para el alcance del
  MVP o si hay que generalizar antes.
- **Nominatim**: política de uso limita a 1 req/seg y exige un
  `User-Agent` identificable con contacto real — configúralo en `.env`
  (`NOMINATIM_USER_AGENT`) antes de usarlo en serio.

## Desplegar en Vercel (validación real + uso sin instalar nada)

Este sandbox no tiene salida a internet a los dominios que usa PisoCheck
(comprobado, incluido vercel.com), así que el despliegue lo tiene que
lanzar quien tenga acceso normal a internet — una vez desplegado, el
código corre en la infraestructura de Vercel, que sí tiene salida real.

Un único punto de entrada, **`api/index.py`** — Vercel exige exactamente
uno por proyecto en cuanto detecta `pyproject.toml` en la raíz (ver
`[tool.vercel]` ahí dentro), así que el análisis real y el diagnóstico
comparten el mismo `handler`, distinguidos por `?modo=`:

- `GET /api/index?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent` — el
  análisis real: pipeline completo, informe HTML con datos reales.
  Admite `&vs=Otra+direccion` para comparar dos pisos.
- `GET /api/index?modo=smoke` — diagnóstico (JSON): geocoder/catastro/osm/
  opendata_vlc contra Garbí 24 y Burjassot 71, comparado con el ground
  truth conocido. Útil si el modo normal da un error raro.

```bash
npm install -g vercel   # o usa npx vercel
vercel login            # login normal en el navegador, sin pegar tokens en ningún sitio
vercel --prod
```

Cuando termine el deploy, entra a `https://<tu-proyecto>.vercel.app/api/index?direccion=Carrer+del+Garb%C3%AD+24%2C+Torrent`
— deberías ver el informe. Si algo no cuadra con lo que ya sabemos de esa
vivienda (§2, ground truth), pégame la URL o el HTML resultante y ajusto
el parser que esté fallando.

⚠️ Sin caché ni límite de peticiones — cada carga repite todas las
llamadas a APIs externas, así que puede tardar unos segundos (`maxDuration`
en `vercel.json` está en 10s, compatible con el plan gratuito; si Overpass
va lento y da timeout, es esperable en esta fase, no un bug del código —
subir el límite requiere plan de pago). Si vas a dejarlo público un
tiempo, ten en cuenta que cualquiera con la URL puede usarlo y consumir
tus cuotas de las APIs.

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # opcional, todo funciona sin claves
pytest -q
ruff check pisocheck tests
```
