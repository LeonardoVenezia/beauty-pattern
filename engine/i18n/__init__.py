"""Textos de los patrones: espanol, ingles, frances, aleman e italiano."""

from __future__ import annotations

from engine.i18n.de import DE
from engine.i18n.en import EN
from engine.i18n.es import ES
from engine.i18n.fr import FR
from engine.i18n.it import IT

CATALOGS: dict[str, dict[str, str]] = {"es": ES, "en": EN, "fr": FR, "de": DE, "it": IT}
AREA_KEYS: dict[str, str] = {}  # clave -> modulo de area que la define


def _load_areas() -> None:
    """Suma los textos de engine/i18n/areas/*.py a los catalogos."""
    import importlib
    import pkgutil

    from engine.i18n import areas

    base = set(ES)
    for info in pkgutil.iter_modules(areas.__path__):
        module = importlib.import_module(f"engine.i18n.areas.{info.name}")
        for lang, texts in module.TEXTS.items():
            for key, text in texts.items():
                if key in base or AREA_KEYS.get(key, info.name) != info.name:
                    raise ValueError(f"clave repetida en el area {info.name}: {key}")
                AREA_KEYS[key] = info.name
                CATALOGS[lang][key] = text


_load_areas()
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
