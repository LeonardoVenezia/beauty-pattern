from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from engine.gauge import DEFAULT_GAUGES, Gauge


def test_basic_conversions() -> None:
    gauge = Gauge(stitches_per_10cm=22, rows_per_10cm=30)
    assert gauge.stitches_for_cm(10) == 22
    assert gauge.rows_for_cm(10) == 30
    assert gauge.stitches_for_cm(50) == 110
    assert gauge.rows_for_cm(5) == 15
    assert gauge.cm_for_stitches(110) == pytest.approx(50)
    assert gauge.cm_for_rows(15) == pytest.approx(5)


def test_rounding_is_half_up() -> None:
    gauge = Gauge(stitches_per_10cm=5, rows_per_10cm=5)
    # 0.5 puntos/cm * 3 cm = 1.5 -> 2
    assert gauge.stitches_for_cm(3) == 2


def test_invalid_gauge() -> None:
    with pytest.raises(ValidationError):
        Gauge(stitches_per_10cm=0, rows_per_10cm=10)
    with pytest.raises(ValidationError):
        Gauge(stitches_per_10cm=10, rows_per_10cm=-1)


def test_negative_inputs() -> None:
    gauge = DEFAULT_GAUGES["dk"]
    with pytest.raises(ValueError):
        gauge.stitches_for_cm(-1)
    with pytest.raises(ValueError):
        gauge.cm_for_stitches(-1)


@settings(max_examples=200)
@given(
    sts=st.floats(min_value=4, max_value=60),
    rows=st.floats(min_value=4, max_value=80),
    cm=st.floats(min_value=0.5, max_value=200),
)
def test_stitch_conversion_error_is_bounded(sts: float, rows: float, cm: float) -> None:
    gauge = Gauge(stitches_per_10cm=sts, rows_per_10cm=rows)
    stitches = gauge.stitches_for_cm(cm)
    error_cm = abs(gauge.cm_for_stitches(stitches) - cm)
    # El error de redondeo no puede superar medio punto convertido a cm.
    assert error_cm <= 0.5 / gauge.stitches_per_cm + 1e-9


def test_default_gauges_positive() -> None:
    for name, gauge in DEFAULT_GAUGES.items():
        assert gauge.stitches_per_10cm > 0, name
        assert gauge.rows_per_10cm > 0, name
