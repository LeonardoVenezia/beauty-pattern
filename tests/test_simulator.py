from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.gauge import Gauge
from engine.ir import (
    CountRef,
    JoinCheck,
    Materials,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Section,
    SectionTarget,
    Step,
    build_step,
)
from engine.simulator import SimulationError, simulate
from engine.spec import (
    Category,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind

DEFAULT_GAUGE = Gauge(stitches_per_10cm=20.0, rows_per_10cm=28.0)


def make_pattern(
    sections: list[Section],
    *,
    measurements: tuple[Measurement, ...] = (),
    joins: tuple[JoinCheck, ...] = (),
    gauge: Gauge = DEFAULT_GAUGE,
) -> Pattern:
    spec = GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.RAGLAN_TOP_DOWN,
    )
    return Pattern(
        meta=PatternMeta(
            id="test",
            family="test",
            title_key="title.test",
            size="M",
            created_at="2026-11-09",
            engine_version="0.1.0",
        ),
        spec=spec,
        params=PatternParams(densidad=gauge),
        sections=tuple(sections),
        measurements=measurements,
        materials=Materials(
            yarn_weight=YarnWeight.DK,
            needle_mm=4.0,
            hook_mm=None,
            meters=100.0,
        ),
        joins=joins,
    )


def knit_section(
    section_id: str = "body",
    *,
    stitches: int = 100,
    rows: int = 2,
    end: int | None = None,
    target: SectionTarget | None = None,
    meta: dict[str, int] | None = None,
    gauge: Gauge = DEFAULT_GAUGE,
) -> Section:
    steps = [
        build_step(number, stitches, (Op(StitchKind.KNIT, times=stitches),))
        for number in range(1, rows + 1)
    ]
    return Section(
        id=section_id,
        name_key="section.body",
        mode="round",
        steps=tuple(steps),
        start_stitches=stitches,
        end_stitches=stitches if end is None else end,
        target=target,
        meta={} if meta is None else meta,
    )


def codes(pattern: Pattern) -> set[str]:
    return {issue.code for issue in simulate(pattern).issues}


def test_valid_pattern_passes() -> None:
    body = knit_section(
        target=SectionTarget(
            measurement_key="body_circumference",
            target_cm=50.0,
            tolerance_cm=0.1,
        )
    )
    report = simulate(
        make_pattern(
            [body],
            measurements=(
                Measurement(
                    key="body_circumference",
                    value_cm=50.0,
                    target_cm=50.0,
                    tolerance_cm=0.1,
                ),
            ),
        )
    )
    assert report.ok
    assert report.final_counts == {"body": 100}
    assert report.sections_checked == 1
    assert report.steps_checked == 2
    assert report.errors == ()
    report.raise_if_failed()


def test_declared_count_mismatch() -> None:
    bad = Step(
        number=1,
        items=(Op(StitchKind.KNIT, times=100),),
        stitch_count_end=99,
    )
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(bad,),
        start_stitches=100,
        end_stitches=100,
    )
    report = simulate(make_pattern([section]))
    assert not report.ok
    assert "declared_count" in {issue.code for issue in report.issues}


def test_row_consumption_mismatch() -> None:
    bad = Step(
        number=1,
        items=(Op(StitchKind.KNIT, times=90),),
        stitch_count_end=10,
    )
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(bad,),
        start_stitches=100,
        end_stitches=10,
    )
    assert "row_consumption" in codes(make_pattern([section]))


def test_section_end_mismatch() -> None:
    section = knit_section(end=90)
    assert "section_end" in codes(make_pattern([section]))


def test_measurement_out_of_tolerance() -> None:
    pattern = make_pattern(
        [knit_section()],
        measurements=(
            Measurement(
                key="body_circumference",
                value_cm=55.0,
                target_cm=50.0,
                tolerance_cm=1.0,
            ),
        ),
    )
    assert "measurement" in codes(pattern)


def test_section_target_out_of_tolerance() -> None:
    section = knit_section(
        target=SectionTarget(
            measurement_key="body_circumference",
            target_cm=60.0,
            tolerance_cm=1.0,
        )
    )
    assert "section_measurement" in codes(make_pattern([section]))


def test_section_length_target() -> None:
    good = knit_section(
        rows=28,
        target=SectionTarget(
            measurement_key="body_length",
            target_cm=10.0,
            tolerance_cm=0.01,
            dimension="length",
        ),
    )
    assert simulate(make_pattern([good])).ok
    bad = knit_section(
        rows=28,
        target=SectionTarget(
            measurement_key="body_length",
            target_cm=20.0,
            tolerance_cm=0.1,
            dimension="length",
        ),
    )
    assert "section_measurement" in codes(make_pattern([bad]))


def test_increase_sum_mismatch() -> None:
    step = build_step(
        1,
        100,
        (Op(StitchKind.M1R, times=4), Op(StitchKind.KNIT, times=100)),
    )
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(step,),
        start_stitches=100,
        end_stitches=104,
        meta={"expected_increases": 5, "expected_decreases": 0},
    )
    assert "increase_sum" in codes(make_pattern([section]))


def test_decrease_sum_mismatch() -> None:
    step = build_step(
        1,
        100,
        (Op(StitchKind.K2TOG, times=4), Op(StitchKind.KNIT, times=92)),
    )
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(step,),
        start_stitches=100,
        end_stitches=96,
        meta={"expected_increases": 0, "expected_decreases": 5},
    )
    assert "decrease_sum" in codes(make_pattern([section]))


def test_lace_counts_both() -> None:
    step = build_step(
        1,
        100,
        (Op(StitchKind.K2TOG, times=10), Op(StitchKind.YO, times=10), Op(StitchKind.KNIT, times=80)),
    )
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(step,),
        start_stitches=100,
        end_stitches=100,
        meta={"expected_increases": 10, "expected_decreases": 10},
    )
    assert simulate(make_pattern([section])).ok


def test_step_order() -> None:
    first = build_step(2, 100, (Op(StitchKind.KNIT, times=100),))
    second = build_step(1, 100, (Op(StitchKind.KNIT, times=100),))
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(first, second),
        start_stitches=100,
        end_stitches=100,
    )
    assert "step_order" in codes(make_pattern([section]))


def test_empty_section_changing_count() -> None:
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(),
        start_stitches=10,
        end_stitches=12,
    )
    assert "empty_section" in codes(make_pattern([section]))


def test_duplicate_section() -> None:
    pattern = make_pattern([knit_section("body"), knit_section("body")])
    assert "duplicate_section" in codes(pattern)


def test_no_sections() -> None:
    assert "no_sections" in codes(make_pattern([]))


def test_join_ok_and_mismatch() -> None:
    body = knit_section("body", stitches=100, meta={"armhole": 40})
    sleeve = knit_section("sleeve", stitches=40)
    join = JoinCheck(
        label_key="join.underarm",
        left=(CountRef("body", "meta:armhole"),),
        right=(CountRef("sleeve", "end"),),
    )
    assert simulate(make_pattern([body, sleeve], joins=(join,))).ok
    bad_sleeve = knit_section("sleeve", stitches=41)
    report = simulate(make_pattern([body, bad_sleeve], joins=(join,)))
    assert "join_mismatch" in {issue.code for issue in report.issues}


def test_join_missing_section_and_field() -> None:
    body = knit_section("body")
    join = JoinCheck(
        label_key="join.underarm",
        left=(CountRef("body", "meta:armhole"),),
        right=(CountRef("ghost", "end"),),
    )
    report = simulate(make_pattern([body], joins=(join,)))
    assert "join_section" in {issue.code for issue in report.issues}

    join_field = JoinCheck(
        label_key="join.underarm",
        left=(CountRef("body", "nope"),),
        right=(CountRef("body", "end"),),
    )
    report = simulate(make_pattern([body], joins=(join_field,)))
    assert "join_field" in {issue.code for issue in report.issues}


def test_raise_if_failed() -> None:
    pattern = make_pattern([knit_section(end=90)])
    with pytest.raises(SimulationError):
        simulate(pattern).raise_if_failed()


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(
    start=st.integers(min_value=1, max_value=300),
    actions=st.lists(
        st.sampled_from(["knit", "inc", "dec", "lace"]),
        min_size=1,
        max_size=30,
    ),
    sts_per_10cm=st.floats(
        min_value=10, max_value=40, allow_nan=False, allow_infinity=False
    ),
    rows_per_10cm=st.floats(
        min_value=10, max_value=50, allow_nan=False, allow_infinity=False
    ),
)
def test_property_valid_patterns_pass(
    start: int,
    actions: list[str],
    sts_per_10cm: float,
    rows_per_10cm: float,
) -> None:
    gauge = Gauge(stitches_per_10cm=sts_per_10cm, rows_per_10cm=rows_per_10cm)
    steps: list[Step] = []
    current = start
    increases = 0
    decreases = 0
    for number, action in enumerate(actions, start=1):
        if action == "inc":
            items = (Op(StitchKind.M1R), Op(StitchKind.KNIT, times=current))
            increases += 1
        elif action == "dec" and current >= 2:
            item_list = [Op(StitchKind.K2TOG)]
            if current > 2:
                item_list.append(Op(StitchKind.KNIT, times=current - 2))
            items = tuple(item_list)
            decreases += 1
        elif action == "lace" and current >= 2:
            item_list = [Op(StitchKind.K2TOG), Op(StitchKind.YO)]
            if current > 2:
                item_list.append(Op(StitchKind.KNIT, times=current - 2))
            items = tuple(item_list)
            increases += 1
            decreases += 1
        else:
            items = (Op(StitchKind.KNIT, times=current),)
        steps.append(build_step(number, current, items))
        current = steps[-1].stitch_count_end

    circumference = current / (sts_per_10cm / 10)
    rows = len(steps)
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=tuple(steps),
        start_stitches=start,
        end_stitches=current,
        target=SectionTarget(
            measurement_key="body_circumference",
            target_cm=circumference,
            tolerance_cm=1e-6,
        ),
        meta={
            "expected_increases": increases,
            "expected_decreases": decreases,
            "row_count": rows,
        },
    )
    pattern = make_pattern(
        [section],
        measurements=(
            Measurement(
                key="body_circumference",
                value_cm=circumference,
                target_cm=circumference,
                tolerance_cm=1e-6,
            ),
            Measurement(
                key="body_length",
                value_cm=rows / (rows_per_10cm / 10),
                target_cm=rows / (rows_per_10cm / 10),
                tolerance_cm=1e-6,
                kind="length",
            ),
        ),
        gauge=gauge,
    )
    report = simulate(pattern)
    assert report.ok, report.issues


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    start=st.integers(min_value=2, max_value=200),
    rows=st.integers(min_value=1, max_value=10),
    offset=st.integers(min_value=1, max_value=5),
)
def test_property_tampered_patterns_fail(
    start: int, rows: int, offset: int
) -> None:
    section = knit_section(stitches=start, rows=rows, end=start + offset)
    assert not simulate(make_pattern([section])).ok


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    body_count=st.integers(min_value=10, max_value=120),
    sleeve_count=st.integers(min_value=10, max_value=120),
)
def test_property_joins(body_count: int, sleeve_count: int) -> None:
    body = knit_section("body", stitches=body_count, meta={"armhole": body_count})
    sleeve = knit_section("sleeve", stitches=sleeve_count)
    join = JoinCheck(
        label_key="join.underarm",
        left=(CountRef("body", "meta:armhole"),),
        right=(CountRef("sleeve", "end"),),
    )
    report = simulate(make_pattern([body, sleeve], joins=(join,)))
    assert report.ok == (body_count == sleeve_count)
