"""Toda clave literal usada en el codigo existe en es y en."""

from __future__ import annotations

import re
from pathlib import Path

from engine.i18n.en import EN
from engine.i18n.es import ES

_ROOT = Path(__file__).resolve().parent.parent
_KEY = re.compile(r"""\bt\(\s*["']([a-z_][a-z0-9_.]+)["']""")


def test_literal_keys_exist_in_both_languages() -> None:
    missing = []
    for folder in ("engine", "render", "api", "ai", "scripts"):
        for path in (_ROOT / folder).rglob("*.py"):
            for key in _KEY.findall(path.read_text(encoding="utf-8")):
                if key not in ES or key not in EN:
                    missing.append(f"{path.relative_to(_ROOT)}: {key}")
    assert not missing, missing


def test_languages_have_same_keys() -> None:
    assert set(ES) == set(EN)
