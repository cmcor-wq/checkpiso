"""Reproduce el fallo real visto en Vercel: una variable de entorno
definida pero vacía (no ausente) no debe tumbar el import de config.py.
"""

import importlib

import pisocheck.config as config_module


def test_cache_ttl_hours_vacio_usa_default(monkeypatch):
    monkeypatch.setenv("CACHE_TTL_HOURS", "")
    reloaded = importlib.reload(config_module)

    assert reloaded.CACHE_TTL_HOURS == 72

    monkeypatch.delenv("CACHE_TTL_HOURS", raising=False)
    importlib.reload(config_module)  # deja config.py como estaba para el resto de tests


def test_nominatim_user_agent_vacio_usa_default(monkeypatch):
    monkeypatch.setenv("NOMINATIM_USER_AGENT", "")
    reloaded = importlib.reload(config_module)

    assert reloaded.NOMINATIM_USER_AGENT == "PisoCheck/0.1"

    monkeypatch.delenv("NOMINATIM_USER_AGENT", raising=False)
    importlib.reload(config_module)
