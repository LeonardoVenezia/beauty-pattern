"""Exactitud del texto multitalle: cada numero cae en su talle y en orden.

El texto con todos los talles se arma fusionando los patrones de cada talle.
Si la fusion corriera un numero de linea o de talle, la tejedora seguiria un
conteo que no es el suyo. Aca se "proyecta" el texto fusionado a cada talle
(eligiendo su valor en cada "a (b, c, ...)" y en cada "Solo talles") y se
comprueba que los conteos [N pts] sean, en orden, los de la IR de ese talle.
"""

from __future__ import annotations

import re

import pytest

from engine.document import build_document
from engine.garments import generate_size_set
from engine.spec import (
    Category,
    Colorwork,
    ColorworkType,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.text import render_document_text

_NUM = r"(?:\d+(?:\.\d+)?|\u2013)"  # numero o guion de "no corresponde"
_SPECS = {
    "raglan": GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=Construction.RAGLAN_TOP_DOWN),
    "yoke": GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.YOKE,
        colorwork=Colorwork(tipo=ColorworkType.FAIR_ISLE, paleta=["azul", "blanco"]),
    ),
    "drop": GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.NEEDLES, construccion=Construction.DROP_SHOULDER),
    "set_in": GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.NEEDLES, construccion=Construction.SET_IN_SLEEVE),
    "cardigan": GarmentSpec(categoria=Category.CARDIGAN, tecnica=Technique.NEEDLES),
    "vest": GarmentSpec(categoria=Category.VEST, tecnica=Technique.NEEDLES),
    "crochet": GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.CROCHET),
}


def _project(text: str, sizes: list[str], size: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        only = re.match(r"\W*Solo talles ([^:]+):", line)
        here = [s.strip() for s in only.group(1).split(",")] if only else sizes
        if size not in here:
            continue
        index = here.index(size)

        def pick(match: re.Match[str], here: list[str] = here, index: int = index, line: str = line) -> str:
            values = [match.group(1), *(v.strip() for v in match.group(2).split(","))]
            assert len(values) == len(here), line
            return values[index]

        lines.append(re.sub(rf"({_NUM}) \(((?:{_NUM}, )*{_NUM})\)", pick, line))
    return lines


@pytest.mark.parametrize("family", list(_SPECS))
@pytest.mark.parametrize("weight", [YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.BULKY])
def test_every_number_of_the_multisize_text_belongs_to_its_size_in_order(family: str, weight: YarnWeight) -> None:
    patterns = generate_size_set(_SPECS[family], PatternParams(peso_hilo=weight))
    sizes = [p.meta.size for p in patterns]
    merged = render_document_text(build_document(patterns))
    for pattern in patterns:
        shown = [int(n) for line in _project(merged, sizes, pattern.meta.size) for n in re.findall(r"\[(\d+) pts\]", line)]
        counts = iter([step.stitch_count_end for section in pattern.sections for step in section.steps])
        assert shown and all(any(n == c for c in counts) for n in shown), pattern.meta.size


def test_mirrored_fronts_may_be_one_row_apart_but_never_one_stitch() -> None:
    from engine.simulator.simulator import _mirrored

    left = [60, 60, 55, 55, 50, 50]
    assert _mirrored(left, [60, 60, 60, 55, 55, 50])  # cierre una hilera despues: correcto
    assert not _mirrored(left, [60, 60, 55, 56, 50, 50])  # un punto de mas
    assert not _mirrored(left, [60, 60, 55, 55, 50, 51])  # termina distinto
