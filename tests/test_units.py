from __future__ import annotations

import pytest

from engine.rounding import clamp, round_half_up
from engine.units import cm_to_inches, format_cm, format_inches, format_length, inches_to_cm


def test_inch_cm_roundtrip() -> None:
    assert inches_to_cm(10) == pytest.approx(25.4)
    assert cm_to_inches(25.4) == pytest.approx(10)
    assert cm_to_inches(inches_to_cm(37.5)) == pytest.approx(37.5)


def test_round_half_up() -> None:
    assert round_half_up(2.5) == 3
    assert round_half_up(2.4999) == 2
    assert round_half_up(0.5) == 1
    with pytest.raises(ValueError):
        round_half_up(float("nan"))


def test_clamp() -> None:
    assert clamp(5, 1, 3) == 3
    assert clamp(-2, 1, 3) == 1
    with pytest.raises(ValueError):
        clamp(1, 3, 1)


def test_format_cm() -> None:
    assert format_cm(56.0) == "56 cm"
    assert format_cm(56.04) == "56 cm"
    assert format_cm(56.25) == "56.2 cm"


def test_format_inches_quarters() -> None:
    assert format_inches(inches_to_cm(10)) == '10"'
    assert format_inches(inches_to_cm(10.25)) == '10 1/4"'
    assert format_inches(inches_to_cm(10.5)) == '10 1/2"'
    assert format_inches(inches_to_cm(10.75)) == '10 3/4"'


def test_format_length_units() -> None:
    assert format_length(25.4, "cm") == "25.4 cm"
    assert format_length(25.4, "in") == '10"'
