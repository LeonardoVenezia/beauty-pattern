"""Textos en espanol e ingles. Los patrones se generan en ambos idiomas."""

from __future__ import annotations

from engine.i18n.en import EN
from engine.i18n.es import ES

CATALOGS: dict[str, dict[str, str]] = {"es": ES, "en": EN}
DEFAULT_LANGUAGE = "es"


def t(key: str, lang: str = DEFAULT_LANGUAGE, **params: object) -> str:
    """Traduce una clave. Si falta, devuelve la clave (visible en tests)."""
    catalog = CATALOGS.get(lang, ES)
    template = catalog.get(key) or ES.get(key) or key
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def has_key(key: str, lang: str) -> bool:
    return key in CATALOGS.get(lang, {})
