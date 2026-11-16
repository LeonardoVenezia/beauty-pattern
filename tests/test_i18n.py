from __future__ import annotations

from engine.i18n import CATALOGS, t
from engine.i18n.en import EN
from engine.i18n.es import ES


def test_catalogs_have_same_keys_and_placeholders() -> None:
    import string

    def names(text: str) -> list[str]:
        return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)

    for lang, catalog in CATALOGS.items():
        assert set(catalog) == set(ES), lang
        for key, text in ES.items():
            assert names(catalog[key]) == names(text), (lang, key)


def test_translation_and_fallback() -> None:
    assert t("pattern.cast_on", "es", n=120) == "Montar 120 puntos."
    assert t("pattern.cast_on", "en", n=120) == "Cast on 120 stitches."
    assert t("pattern.cast_on", "pt", n=1) == "Montar 1 puntos."
    assert t("clave.inexistente") == "clave.inexistente"


def test_all_languages_registered() -> None:
    from engine.spec import LANGUAGES

    assert set(CATALOGS) == set(LANGUAGES)


def test_operation_keys_for_every_stitch_kind() -> None:
    from engine.stitches.kinds import StitchKind

    for kind in StitchKind:
        if kind.value == "turn":
            continue
        assert f"op.{kind.value}.one" in ES, kind
        assert f"op.{kind.value}.run" in ES, kind
        assert f"op.{kind.value}.one" in EN, kind
        assert f"op.{kind.value}.run" in EN, kind
