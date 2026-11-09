from __future__ import annotations

import pytest

from engine.ir import (
    CountRef,
    JoinCheck,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    build_step,
)
from engine.spec import Category, GarmentSpec, PatternParams, YarnWeight
from engine.stitches.kinds import StitchKind


def test_op_effects() -> None:
    assert Op(StitchKind.KNIT, times=8).consumes == 8
    assert Op(StitchKind.K2TOG, times=3).consumes == 6
    assert Op(StitchKind.K2TOG, times=3).produces == 3
    assert Op(StitchKind.YO).consumes == 0
    assert Op(StitchKind.M1L).produces == 1
    assert Op(StitchKind.CABLE_FRONT, width=4).consumes == 4
    assert Op(StitchKind.CABLE_FRONT, width=4, times=2).produces == 8
    assert Op(StitchKind.MAGIC_RING).produces == 6


def test_invalid_op() -> None:
    with pytest.raises(ValueError):
        Op(StitchKind.KNIT, times=0)
    with pytest.raises(ValueError):
        Op(StitchKind.CABLE_FRONT, width=3)
    with pytest.raises(ValueError):
        Op(StitchKind.CABLE_FRONT)


def test_repeat_effects() -> None:
    repeat = Repeat(times=6, ops=(Op(StitchKind.K2TOG), Op(StitchKind.YO)))
    assert repeat.consumes == 12
    assert repeat.produces == 12


def test_build_step_computes_end() -> None:
    step = build_step(1, 100, [Op(StitchKind.KNIT, times=84), Op(StitchKind.K2TOG, times=8)])
    assert step.stitch_count_end == 92
    assert step.consumes == 100


def test_build_step_rejects_wrong_consumption() -> None:
    with pytest.raises(ValueError):
        build_step(1, 100, [Op(StitchKind.KNIT, times=99)])


def test_expanded_ops() -> None:
    step = Step(
        number=1,
        items=(Repeat(2, (Op(StitchKind.KNIT, times=2), Op(StitchKind.K2TOG))),),
        stitch_count_end=4,
    )
    assert [op.kind for op in step.expanded_ops()] == [
        StitchKind.KNIT,
        StitchKind.KNIT,
        StitchKind.K2TOG,
        StitchKind.KNIT,
        StitchKind.KNIT,
        StitchKind.K2TOG,
    ]


def test_section_count_for() -> None:
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(),
        start_stitches=100,
        end_stitches=120,
        meta={"underarm_cast_on": 10},
    )
    assert section.count_for("start") == 100
    assert section.count_for("end") == 120
    assert section.count_for("meta:underarm_cast_on") == 10
    with pytest.raises(KeyError):
        section.count_for("meta:missing")
    with pytest.raises(ValueError):
        section.count_for("other")


def test_pattern_helpers() -> None:
    section = Section(
        id="body",
        name_key="section.body",
        mode="round",
        steps=(),
        start_stitches=100,
        end_stitches=100,
    )
    pattern = Pattern(
        meta=PatternMeta(
            id="p1",
            family="raglan",
            title_key="title.pullover_raglan",
            size="M",
            created_at="2026-01-01T00:00:00+00:00",
            engine_version="0.1.0",
        ),
        spec=GarmentSpec(categoria=Category.PULLOVER),
        params=PatternParams(),
        sections=(section,),
        measurements=(Measurement(key="bust", value_cm=100),),
        materials=__import__("engine.ir", fromlist=["Materials"]).Materials(
            yarn_weight=YarnWeight.DK,
            needle_mm=4.0,
            hook_mm=None,
            meters=1000,
        ),
        joins=(
            JoinCheck(
                label_key="join.test",
                left=(CountRef("body", "start"),),
                right=(CountRef("body", "end"),),
            ),
        ),
    )
    assert pattern.section("body") is section
    assert pattern.total_steps == 0
    with pytest.raises(KeyError):
        pattern.section("missing")
    assert pattern.joins[0].left[0].field == "start"
    assert SectionTarget("bust", 100.0).tolerance_cm == 1.0
