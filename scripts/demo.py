"""Demo end-to-end del motor: especificacion -> patron verificado -> PDF/SVG."""

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
from render.schematic import render_raglan_schematic_svg


def main() -> int:
    spec = GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.RAGLAN_TOP_DOWN,
    )
    params = PatternParams(talla="M")
    pattern = generate(spec, params)
    report = simulate(pattern)
    if not report.ok:
        for issue in report.issues:
            print(f"ERROR {issue.code}: {issue.message}")
        return 1
    output = Path("data/demo")
    output.mkdir(parents=True, exist_ok=True)
    (output / "patron.txt").write_text(render_pattern_text(pattern), encoding="utf-8")
    (output / "esquema.svg").write_text(
        render_raglan_schematic_svg(pattern), encoding="utf-8"
    )
    (output / "patron.pdf").write_bytes(render_pattern_pdf(pattern))
    print(f"Patron generado en {output} (talle {pattern.meta.size})")
    print(f"Secciones: {', '.join(section.id for section in pattern.sections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
