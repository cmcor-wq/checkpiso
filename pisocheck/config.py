"""Configuración: claves de API, rutas y constantes.

Todas las claves son opcionales: las fuentes que las requieren degradan
graceful — devuelven "no disponible" en lugar de fallar el análisis entero.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY: str | None = os.getenv("GOOGLE_PLACES_API_KEY") or None
NASA_EARTHDATA_TOKEN: str | None = os.getenv("NASA_EARTHDATA_TOKEN") or None

NOMINATIM_USER_AGENT: str = os.getenv("NOMINATIM_USER_AGENT", "PisoCheck/0.1")

CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", ".pisocheck_cache"))
CACHE_TTL_HOURS: int = int(os.getenv("CACHE_TTL_HOURS", "72"))

OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./informes"))

HTTP_TIMEOUT_SECONDS: float = 15.0

# Umbral por debajo del cual un factor se marca como alerta en el informe.
ALERTA_SCORE_THRESHOLD: float = 4.0


def has_google_places() -> bool:
    return GOOGLE_PLACES_API_KEY is not None


def has_nasa_earthdata() -> bool:
    return NASA_EARTHDATA_TOKEN is not None
