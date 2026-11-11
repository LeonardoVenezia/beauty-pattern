"""El patron de todos los talles contiene exactamente el de cada talle."""

from __future__ import annotations

import pytest

from engine.blocks import Block, BlockKind, build_pattern_blocks
from engine.garments import generate
from engine.i18n import t
from engine.multisize import format_values, merge_size_blocks, project_to_size, split_numbers
from engine.sizes import BODY_SIZES
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique

SIZES = list(BODY_SIZES)
_UNION = {BlockKind.GLOSSARY, BlockKind.WARNING}

GARMENTS = [
    GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=c)
    for c in (
        Construction.RAGLAN_TOP_DOWN,
        Construction.YOKE,
        Construction.SET_IN_SLEEVE,
        Construction.DROP_SHOULDER,
    )
] + [
    GarmentSpec(categoria=Category.CARDIGAN, tecnica=Technique.NEEDLES),
    GarmentSpec(categoria=Category.VEST, tecnica=Technique.NEEDLES),
    GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.RAGLAN_TOP_DOWN,
        texturas=[{"textura": "cables"}],
    ),
]


def _texts(block: Block) -> tuple[str, str, str]:
    return (block.text, block.label or "", block.value or "")


def _project(merged: tuple[Block, ...], index: int) -> list[tuple[str, str, str]]:
    prefix_of = {
        ", ".join(SIZES[i] for i in present): present
        for present in _subsets()
    }
    out = []
    for block in merged:
        if block.kind in _UNION:
            continue
        text, label, value = _texts(block)
        local = index
        marker = t("pattern.only_sizes", "es", sizes="\x00").split("\x00")
        if text.startswith(marker[0]) and block.kind in {
            BlockKind.STEP,
            BlockKind.REPEAT,
            BlockKind.LINE,
        }:
            head, _, rest = text[len(marker[0]) :].partition(marker[1])
            present = prefix_of[head]
            if index not in present:
                continue
            local = present.index(index)
            text = rest.lstrip()
        out.append(
            (project_to_size(text, local), project_to_size(label, local), project_to_size(value, local))
        )
    return out


def _subsets() -> list[list[int]]:
    from itertools import combinations

    result = []
    for size in range(1, len(SIZES) + 1):
        result.extend(list(combo) for combo in combinations(range(len(SIZES)), size))
    return result


@pytest.mark.parametrize("spec", GARMENTS, ids=lambda s: f"{s.categoria.value}-{s.construccion}")
def test_merged_pattern_projects_back_to_every_size(spec: GarmentSpec) -> None:
    per_size = [
        build_pattern_blocks(generate(spec, PatternParams(talla=s)), size_subtitle=False)
        for s in SIZES
    ]
    merged = merge_size_blocks(per_size, SIZES, "es")
    for index, blocks in enumerate(per_size):
        expected = [_texts(b) for b in blocks if b.kind not in _UNION]
        assert _project(merged, index) == expected, SIZES[index]
    merged_union = {b for b in merged if b.kind in _UNION}
    assert merged_union == {b for blocks in per_size for b in blocks if b.kind in _UNION}


def test_format_values_collapses_equal_numbers() -> None:
    assert format_values(("10", "10", "10")) == "10"
    assert format_values(("88", "96", "100")) == "88 (96, 100)"


def test_split_ignores_abbreviation_digits() -> None:
    shape, numbers = split_numbers("m1l, 20 d, 2pj, 1 d [84 p]")
    assert numbers == ("20", "1", "84")
    assert "m1l" in shape and "2pj" in shape
