from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from engine.stitches.catalog import STITCH_PATTERNS, get_stitch
from render.chart import render_stitch_chart_svg

NS = "{http://www.w3.org/2000/svg}"


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_every_pattern_renders_valid_svg() -> None:
    for pattern in STITCH_PATTERNS.values():
        svg = render_stitch_chart_svg(pattern, repeats=2)
        root = parse(svg)
        assert root.tag == f"{NS}svg"
        title = root.find(f"{NS}title")
        assert title is not None and title.text
        texts = [element.text for element in root.iter(f"{NS}text")]
        assert any(text and text.strip() for text in texts)


def test_stockinette_chart_has_two_rows_and_purl_legend() -> None:
    pattern = get_stitch("stockinette")
    svg = render_stitch_chart_svg(pattern, repeats=2)
    root = parse(svg)
    rects = root.findall(f"{NS}rect")
    # Fondo + 2 filas x 2 repeticiones + leyenda.
    assert len(rects) >= 1 + 4
    labels = " ".join(element.text or "" for element in root.iter(f"{NS}text"))
    assert "revés" in labels


def test_repeats_change_width() -> None:
    pattern = get_stitch("rib_2x2")
    one = parse(render_stitch_chart_svg(pattern, repeats=1))
    three = parse(render_stitch_chart_svg(pattern, repeats=3))
    assert float(three.attrib["width"]) > float(one.attrib["width"])


def test_cable_chart_has_arrow() -> None:
    svg = render_stitch_chart_svg(get_stitch("cable_2x2_front"), repeats=2)
    root = parse(svg)
    assert root.findall(f"{NS}polygon")


def test_crochet_chart() -> None:
    svg = render_stitch_chart_svg(get_stitch("crochet_sc"), repeats=6)
    root = parse(svg)
    assert root.findall(f"{NS}line")
    labels = " ".join(element.text or "" for element in root.iter(f"{NS}text"))
    assert "punto bajo" in labels


def test_round_chart_uses_round_rows() -> None:
    pattern = get_stitch("stockinette")
    svg = render_stitch_chart_svg(pattern, repeats=2, in_the_round=True)
    root = parse(svg)
    labels = " ".join(element.text or "" for element in root.iter(f"{NS}text"))
    # En redondo, jersey no tiene reves.
    assert "revés" not in labels


def test_invalid_repeats() -> None:
    with pytest.raises(ValueError):
        render_stitch_chart_svg(get_stitch("stockinette"), repeats=0)


def test_english_chart() -> None:
    svg = render_stitch_chart_svg(get_stitch("stockinette"), lang="en")
    assert "purl" in svg
