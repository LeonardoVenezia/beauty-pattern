"""Genera ejemplos deterministas para revisar el motor y los renders."""

from __future__ import annotations

from pathlib import Path

from engine.garments import generate
from engine.simulator import simulate
from engine.spec import (
    Category,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
)
from engine.text import render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg


def main() -> int:
    output = Path("data/ejemplos")
    output.mkdir(parents=True, exist_ok=True)
    examples = [
        (
            "raglan",
            GarmentSpec(
                categoria=Category.PULLOVER,
                tecnica=Technique.CIRCULAR,
                construccion=Construction.RAGLAN_TOP_DOWN,
            ),
            PatternParams(talla="M"),
        ),
        (
            "gorro",
            GarmentSpec(categoria=Category.HAT, tecnica=Technique.CIRCULAR),
            PatternParams(talla="M"),
        ),
        (
            "amigurumi",
            GarmentSpec(categoria=Category.AMIGURUMI, tecnica=Technique.CROCHET),
            PatternParams(peso_hilo="dk"),
        ),
        (
            "granny",
            GarmentSpec(categoria=Category.BLANKET, tecnica=Technique.CROCHET),
            PatternParams(peso_hilo="dk", dimensiones_cm={"size": 15.0}),
        ),
    ]
    for name, spec, params in examples:
        pattern = generate(spec, params)
        report = simulate(pattern)
        if not report.ok:
            for issue in report.issues:
                print(f"{name}: ERROR {issue.code}: {issue.message}")
            return 1
        (output / f"{name}.txt").write_text(
            render_pattern_text(pattern), encoding="utf-8"
        )
        (output / f"{name}.svg").write_text(
            render_schematic_svg(pattern), encoding="utf-8"
        )
        (output / f"{name}.pdf").write_bytes(render_pattern_pdf(pattern))
        print(f"{name}: {', '.join(section.id for section in pattern.sections)}")
    print(f"Ejemplos en {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
