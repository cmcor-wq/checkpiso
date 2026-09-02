# PisoCheck

Análisis automatizado de viviendas con datos públicos españoles. Dada una
dirección, cruza catastro, urbanismo, transporte, ocio, quejas vecinales,
zonas verdes, etc. y genera una puntuación de zona explicada de forma
narrativa. Ver la especificación completa en el documento original del
proyecto.

## Estado — Sesiones 1 y 2 completadas

**Sesión 1** — fuentes de datos base:
- `pisocheck/models.py` — `AddressData`, `FactorResult`, `ReportData`.
- `pisocheck/geocoder.py` — dirección → lat/lng/municipio/distrito/barrio (Nominatim).
- `pisocheck/sources/catastro.py` — Consulta_DNPPP (Sede Catastro OVC, sin auth).
- `pisocheck/sources/opendata_vlc.py` — quejas/sugerencias por distrito (solo Valencia ciudad).
- `pisocheck/sources/osm.py` — Overpass: farolas, ocio nocturno, transporte, colegios, farmacias, supermercados, parques, parking.

**Sesión 2** — motor de puntuación:
- `pisocheck/scoring/factors.py` — funciones `score_*` para 11 de los 14 factores (ver tabla abajo).
- `pisocheck/scoring/engine.py` — `build_report(address, raw_data)`: arma el `ReportData` con los factores disponibles, omite los que faltan (no rompe la media).
- `pisocheck/sources/solar.py` — PVGIS real (horas de sol equivalentes/día).
- `pisocheck/sources/places.py` — Google Places Nearby Search, con degradación graceful (`None`) si no hay `GOOGLE_PLACES_API_KEY`.

32 tests con `pytest-httpx` (mocks), usando como ground truth los datos reales de Garbí 24 y Av. Burjassot 71.

### Cobertura de los 14 factores ahora mismo

| Factor | Estado |
|---|---|
| Ocio nocturno, Transporte, Zona verde, Iluminación, Colegios, Aparcamiento, Comercio, Salud/farmacias | ✅ Fuente OSM + scoring (parcial: sin el matiz de horario/24h que daría Places) |
| Quejas vecinales | ✅ Solo Valencia ciudad (Open Data VLC); Torrent sin fuente (GIVP no implementado) |
| Sol y orientación | ✅ PVGIS, orientación sur asumida por defecto |
| Riesgo inundación | ⚠️ Scoring listo, sin fuente (`sources/inundacion.py`, SNCZI — sesión 4) |
| Ruido nocturno, Ruido aeronáutico, Limpieza zona | ❌ Sin fuente ni scoring todavía (sesión 4, ver riesgos abajo) |

Pendiente (sesiones 3-4 del roadmap original): generación de informes
HTML/PDF, CLI (`main.py`), cache SQLite, SNCZI/inundación, NASA Black
Marble, ruido aeronáutico, mercado inmobiliario.

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

## Validación en vivo — opción Vercel

`api/smoke.py` es el mismo chequeo que `scripts/smoke_test.py` pero como
endpoint HTTP, pensado para desplegarlo en Vercel (que sí tiene salida real
a internet, a diferencia de este sandbox — comprobado, Vercel también está
bloqueado desde aquí). Es temporal: no forma parte de la arquitectura CLI
final, solo sirve para validar las fuentes de datos.

```bash
npm install -g vercel   # o usa npx vercel
vercel login            # login normal, no compartas tokens en texto plano
vercel --prod
```

Cuando termine el deploy, visita `https://<tu-proyecto>.vercel.app/api/smoke`
y pégame el JSON de vuelta. **Borra el proyecto de Vercel (o al menos este
endpoint) en cuanto termines de validar** — es público, sin autenticación,
y solo tiene sentido como herramienta de depuración puntual.

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # opcional, todo funciona sin claves
pytest -q
ruff check pisocheck tests
```
