from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.gauge import Gauge
from engine.sizes import BODY_SIZES, ease_for_fit, resolve_body_size
from engine.spec import (
    Category,
    Fit,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
    resolve_gauge,
)


def test_minimal_spec() -> None:
    spec = GarmentSpec(categoria=Category.PULLOVER)
    assert spec.tecnica is Technique.NEEDLES
    assert spec.texturas == []
    assert spec.colorwork is None


def test_spec_rejects_unknown_enum() -> None:
    with pytest.raises(ValidationError):
        GarmentSpec(categoria="sweater")  # type: ignore[arg-type]


def test_spec_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GarmentSpec(categoria=Category.HAT, medidas="grande")  # type: ignore[call-arg]


def test_confidence_range() -> None:
    with pytest.raises(ValidationError):
        GarmentSpec(categoria=Category.HAT, confianza={"categoria": 1.5})
    spec = GarmentSpec(categoria=Category.HAT, confianza={"categoria": 0.8})
    assert spec.confianza["categoria"] == 0.8


def test_params_validation() -> None:
    with pytest.raises(ValidationError):
        PatternParams(medidas_cm={"bust": -1})
    with pytest.raises(ValidationError):
        PatternParams(ease_cm=100)
    params = PatternParams(densidad=Gauge(stitches_per_10cm=20, rows_per_10cm=28))
    assert params.idioma == "es"
    assert resolve_gauge(params).stitches_per_10cm == 20


def test_resolve_gauge_defaults_by_weight() -> None:
    assert resolve_gauge(PatternParams(peso_hilo=YarnWeight.WORSTED)).stitches_per_10cm == 18
    assert resolve_gauge(PatternParams(peso_hilo=YarnWeight.UNKNOWN)).stitches_per_10cm == 22


def test_size_table_and_overrides() -> None:
    assert set(BODY_SIZES) == {"XS", "S", "M", "L", "XL", "2XL", "3XL"}
    size = resolve_body_size("m")
    assert size.key == "M"
    custom = resolve_body_size("M", {"bust": 101.0, "body_length": 61.0})
    assert custom.bust_cm == 101.0
    assert custom.body_length_cm == 61.0
    assert custom.hip_cm == size.hip_cm
    with pytest.raises(ValueError):
        resolve_body_size("XXS")
    with pytest.raises(ValueError):
        resolve_body_size("M", {"cabeza": 50.0})


def test_ease() -> None:
    assert ease_for_fit(Fit.FITTED) < 0
    assert ease_for_fit(Fit.REGULAR) == 6.0
    assert ease_for_fit(None) == 6.0
