"""Escotes con tapa (henley, polo) y cuello chal para las prendas en piezas.

- Henley y polo: el delantero se abre en el centro unas hileras antes del
  escote (se cierran los pts de la tapa) y cada lado se teje por separado,
  con su escote redondo; dos tapas de santa clara se cosen a la abertura, una
  con ojales. El polo lleva un cuello de elastico en lugar de la tira.
- Cuello chal (cardigan/saco): delanteros con escote en V; en vez de tiras de
  botones y cuello, dos mitades de cuello de santa clara que se ensanchan a
  lo largo de la V y se unen en el centro de la espalda.

ASUNCIONES (docs/fuentes.md): abertura de la tapa 8 cm debajo del escote,
tapa de 2,5 cm de ancho, 3 botones; cuello chal de 10 cm de ancho.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.distribution import regular_rows
from engine.garments.rows import FlatRows, front_neck_rows
from engine.gauge import Gauge
from engine.ir import Item, Op, Section, SectionTarget, Step, build_step
from engine.rounding import round_half_up
from engine.stitches.kinds import StitchKind

PLACKET_CM = 8.0
PLACKET_BAND_CM = 2.5
BUTTONS = 3
SHAWL_COLLAR_CM = 10.0


@dataclass(frozen=True)
class Placket:
    rows: int  # hileras rectas de cada lado, desde la abertura hasta el escote
    width: int  # pts centrales que se cierran (= ancho de cada tapa)


def plan_placket(gauge: Gauge, center_bo: int, rows_available: int) -> Placket | None:
    """Tapa que entra en el cierre central del escote, o None si no entra."""
    width = max(4, round_half_up(PLACKET_BAND_CM * gauge.stitches_per_cm))
    width -= (center_bo - width) % 2  # el resto del centro se reparte parejo
    if width < 3 or width > center_bo:
        return None
    rows = min(gauge.rows_for_cm(PLACKET_CM), rows_available)
    if rows < 4:
        return None
    return Placket(rows=rows, width=width)


def placket_sides(
    before: int,
    after: int,
    placket: Placket,
    rows: int,
    neck_depth: int,
    neck_bind_off: int,
    neck_decs: int,
) -> tuple[Section, Section]:
    """Los dos lados del delantero despues de abrir la tapa: recto y despues
    el escote redondo (cierre en el borde del centro y disminuciones)."""
    sections = []
    for side_id, sts, at_start, intro in (
        ("neck_right", after, True, "garments.note.placket_side_first"),
        ("neck_left", before, False, "garments.note.placket_side_second"),
    ):
        side = FlatRows(sts, first_number=2)
        for _ in range(rows - neck_depth):
            side.plain()
        front_neck_rows(side, neck_depth, neck_bind_off, neck_decs, neck_at_start=at_start, spread=False)
        sections.append(
            Section(
                id=side_id,
                name_key=f"garments.section.placket_{side_id.removeprefix('neck_')}",
                mode="flat",
                steps=tuple(side.steps),
                start_stitches=sts,
                end_stitches=side.current,
                meta={"row_count": len(side.steps)},
                bind_off=True,
                note_keys=(intro,),
            )
        )
    return sections[0], sections[1]


def _garter(stitches: int) -> tuple[Item, ...]:
    return (Op(StitchKind.KNIT, times=stitches),)


def placket_band(side: str, stitches: int, rows: int, *, buttonholes: bool) -> Section:
    """Tapa de santa clara tejida a lo largo (se cose a la abertura)."""
    steps: list[Step] = [
        build_step(1, 0, (Op(StitchKind.CAST_ON, times=stitches),), note_key="pattern.note.cast_on_panel")
    ]
    holes = {round_half_up((i + 0.5) * rows / BUTTONS) + 1 for i in range(BUTTONS)} if buttonholes else set()
    left = (stitches - 2) // 2
    for number in range(2, rows + 2):
        if number in holes:
            items: tuple[Item, ...] = (
                *((Op(StitchKind.KNIT, times=left),) if left else ()),
                Op(StitchKind.YO),
                Op(StitchKind.K2TOG),
                *((Op(StitchKind.KNIT, times=stitches - 2 - left),) if stitches - 2 - left else ()),
            )
            note = "garments.note.buttonhole" if number == min(holes) else None
        else:
            items, note = _garter(stitches), ("garments.note.placket_band" if number == 2 else None)
        steps.append(build_step(number, stitches, items, note_key=note))
    return Section(
        id=f"placket_{side}",
        name_key=f"garments.section.placket_band_{side}",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=stitches,
        meta={"row_count": rows, "cast_on": stitches, "buttonholes": len(holes)},
        bind_off=True,
    )


def shawl_collar_half(
    side: str, band: int, collar: int, straight_rows: int, v_rows: int, back_rows: int, target_cm: float
) -> Section:
    """Media cuello chal de santa clara, tejida a lo largo desde el borde
    inferior: recta junto al delantero, se ensancha a lo largo de la V con
    aumentos en el borde libre y sigue recta hasta el centro de la espalda."""
    incs = collar - band
    if incs < 0 or incs > v_rows:
        raise ValueError("cuello chal: no entran los aumentos")
    at = {straight_rows + r for r in regular_rows(v_rows, incs)} if incs else set()
    steps: list[Step] = [
        build_step(1, 0, (Op(StitchKind.CAST_ON, times=band),), note_key="pattern.note.cast_on_panel")
    ]
    current = band
    total = straight_rows + v_rows + back_rows
    for row in range(1, total + 1):
        if row in at:
            items: tuple[Item, ...] = (
                (Op(StitchKind.KNIT), Op(StitchKind.M1R), Op(StitchKind.KNIT, times=current - 1))
                if side == "right"
                else (Op(StitchKind.KNIT, times=current - 1), Op(StitchKind.M1L), Op(StitchKind.KNIT))
            )
            note = "garments.note.shawl_collar_increase" if row == min(at) else None
            steps.append(build_step(row + 1, current, items, note_key=note))
            current += 1
        else:
            note = "garments.note.shawl_collar" if row == 1 else (
                "garments.note.shawl_collar_back" if row == straight_rows + v_rows + 1 else None
            )
            steps.append(build_step(row + 1, current, _garter(current), note_key=note))
    return Section(
        id=f"shawl_collar_{side}",
        name_key=f"garments.section.shawl_collar_{side}",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=current,
        target=SectionTarget(
            measurement_key=f"shawl_collar_{side}_length", target_cm=target_cm, tolerance_cm=1.0, dimension="length"
        ),
        meta={"row_count": total, "cast_on": band},
        bind_off=True,
    )
