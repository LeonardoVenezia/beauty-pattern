from __future__ import annotations

from engine.garments import generate
from engine.serialization import (
    pattern_from_dict,
    pattern_from_json,
    pattern_to_dict,
    pattern_to_json,
)
from engine.simulator import simulate
from engine.spec import (
    Category,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
)


def test_pattern_json_roundtrip() -> None:
    pattern = generate(
        GarmentSpec(
            categoria=Category.PULLOVER,
            tecnica=Technique.CIRCULAR,
            construccion=Construction.RAGLAN_TOP_DOWN,
        ),
        PatternParams(talla="M"),
    )
    restored = pattern_from_dict(pattern_to_dict(pattern))
    assert restored.meta == pattern.meta
    assert restored.spec == pattern.spec
    assert restored.params == pattern.params
    assert restored.sections == pattern.sections
    assert restored.measurements == pattern.measurements
    assert restored.materials == pattern.materials
    assert restored.warnings == pattern.warnings
    assert restored.joins == pattern.joins
    assert simulate(restored).ok
    assert pattern_from_json(pattern_to_json(pattern)).sections == pattern.sections
