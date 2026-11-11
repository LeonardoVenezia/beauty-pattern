"""Acumulador de hileras planas: LD en hileras impares, LR en pares.

La hilera 1 es el montaje. Lo comparten las prendas en piezas (manga
encajada, hombro caido, cardigan, chaleco) para que el jersey plano tenga
siempre el reves al reves.
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.garments.panels import Panel
from engine.ir import Item, Op, Section, Step, build_step
from engine.stitches.catalog import StitchPattern, expand_row, get_stitch
from engine.stitches.kinds import StitchKind


def hem_rib(stitches: int) -> StitchPattern:
    """Elastico que entra justo: 2x2, 1x1 o santa clara si el numero es impar."""
    if stitches % 4 == 0:
        return get_stitch("rib_2x2")
    if stitches % 2 == 0:
        return get_stitch("rib_1x1")
    return get_stitch("garter")


class FlatRows:
    """Acumula hileras planas alternando LD (impares) y LR (pares).

    Con `start_panel` lleva un panel de textura: guarda cuantos pts lisos hay
    a cada lado (vistos del LD) para que el panel no se mueva cuando se
    cierran o disminuyen pts en los bordes (sisa, copa).
    """

    def __init__(self, start: int, first_number: int = 1) -> None:
        self.current = start
        self.number = first_number
        self.steps: list[Step] = []
        self.panel: Panel | None = None
        self.left = 0
        self.right = 0
        self.chart_row = 1
        self.first_chart_row = 1

    @property
    def right_side(self) -> bool:
        return self.number % 2 == 1

    def add(self, items: Sequence[Item], note: str | None = None) -> None:
        kept = [item for item in items if not (isinstance(item, Op) and item.times == 0)]
        step = build_step(self.number, self.current, kept, note_key=note)
        self.steps.append(step)
        self.current = step.stitch_count_end
        self.number += 1
        if self.panel is not None:
            self.chart_row = self.chart_row % self.panel.rows + 1

    def start_panel(self, panel: Panel) -> None:
        self.panel = panel
        self.left = (self.current - panel.width) // 2
        self.right = self.current - panel.width - self.left
        # Las hileras impares del grafico son del LD.
        self.chart_row = 1 if self.right_side else panel.rows
        self.first_chart_row = self.chart_row

    def row(
        self,
        *,
        bind_off: int = 0,
        decrease: bool = False,
        dec_start: bool = False,
        dec_end: bool = False,
        note: str | None = None,
    ) -> None:
        """Hilera de jersey (con panel si hay): cierre al inicio y/o una
        disminucion en cada borde (`decrease`) o en uno (`dec_start`,
        `dec_end`); las disminuciones van en hileras del LD."""
        if decrease:
            dec_start = dec_end = True
        if (dec_start or dec_end) and not self.right_side:
            raise ValueError("las disminuciones de borde van en hileras del LD")
        knit = StitchKind.KNIT if self.right_side else StitchKind.PURL
        items: list[Item] = []
        if bind_off:
            items.append(Op(StitchKind.BIND_OFF, times=bind_off))
        if self.panel is None:
            middle = self.current - bind_off - (3 if dec_start else 0) - (3 if dec_end else 0)
            if dec_start:
                items += [Op(StitchKind.KNIT), Op(StitchKind.SSK)]
            items.append(Op(knit, times=middle))
            if dec_end:
                items += [Op(StitchKind.K2TOG), Op(StitchKind.KNIT)]
            self.add(items, note)
            return
        if dec_start != dec_end:
            raise ValueError("con panel solo se disminuye en los dos bordes")
        if self.right_side:
            self.left -= bind_off
            if decrease:
                items += [Op(StitchKind.KNIT), Op(StitchKind.SSK)]
            items.append(Op(StitchKind.KNIT, times=self.left - (3 if decrease else 0)))
            items.extend(self.panel.flat_items(self.chart_row))
            items.append(Op(StitchKind.KNIT, times=self.right - (3 if decrease else 0)))
            if decrease:
                items += [Op(StitchKind.K2TOG), Op(StitchKind.KNIT)]
                self.left -= 1
                self.right -= 1
        else:
            self.right -= bind_off
            items.append(Op(StitchKind.PURL, times=self.right))
            items.extend(self.panel.flat_items(self.chart_row))
            items.append(Op(StitchKind.PURL, times=self.left))
        self.add(items, note)

    def plain(self, note: str | None = None) -> None:
        self.row(note=note)

    def bind_off_start(self, count: int, note: str | None = None) -> None:
        self.row(bind_off=count, note=note)

    def decrease_edges(self, note: str | None = None) -> None:
        self.row(decrease=True, note=note)

    def increase_edges(self, note: str | None = None) -> None:
        if self.panel is not None:
            raise ValueError("aumentos de borde con panel no soportados")
        self.add(
            (
                Op(StitchKind.KNIT),
                Op(StitchKind.M1L),
                Op(StitchKind.KNIT, times=self.current - 2),
                Op(StitchKind.M1R),
                Op(StitchKind.KNIT),
            ),
            note,
        )

    def split_for_neck(self, center: int, note: str | None = None) -> tuple[int, int]:
        """Hilera del LD que cierra los `center` pts del medio para el escote.

        Devuelve (pts antes del cierre, pts despues). El panel termina aca:
        sus pts centrales se cierran y el resto sigue en jersey.
        """
        if not self.right_side:
            self.plain()
        self.panel = None
        before = (self.current - center) // 2
        after = self.current - center - before
        self.add(
            (
                Op(StitchKind.KNIT, times=before),
                Op(StitchKind.BIND_OFF, times=center),
                Op(StitchKind.KNIT, times=after),
            ),
            note,
        )
        return before, after

    def panel_meta(self, start: int, segment: int) -> dict[str, int]:
        if self.panel is None:
            return {}
        return {
            "panel_rows": self.panel.rows,
            "panel_repeats": self.panel.repeats,
            "panel_width": self.panel.width,
            "panel_start": start,
            "panel_segment": segment,
            "panel_first_chart_row": self.first_chart_row,
        }


def rib_rows(rows: FlatRows, pattern: StitchPattern, count: int, note: str | None) -> None:
    for index in range(count):
        rows.add(expand_row(pattern, rows.current, index + 1), note if index == 0 else None)


def neck_side(stitches: int, decreases: int, rows: int, *, neck_at_start: bool) -> list[Step]:
    """Un hombro del escote redondo, despues de cerrar el centro.

    Empieza con una hilera del LR. Disminuye 1 pt en el borde del escote en
    las primeras `decreases` hileras del LD y sigue recto hasta `rows`.
    """
    side = FlatRows(stitches, first_number=2)
    done = 0
    for _ in range(rows):
        if side.right_side and done < decreases:
            side.row(dec_start=neck_at_start, dec_end=not neck_at_start, note="pattern.note.neck_decrease" if done == 0 else None)
            done += 1
        else:
            side.plain()
    if done < decreases:
        raise ValueError("no entran las disminuciones del escote")
    return side.steps


NECK_DEPTH_CM = 7.0


def plan_crew_neck(neck_center: int, rows_available: int, rows_per_cm: float) -> tuple[int, int, int]:
    """(hileras de escote, disminuciones por lado, pts centrales a cerrar).

    ASUNCION: 7 cm de profundidad; 20 % del ancho del escote se disminuye por
    lado (1 pt por hilera del LD) y el resto se cierra de una vez.
    """
    depth = min(max(1, round(NECK_DEPTH_CM * rows_per_cm)), rows_available)
    if depth < 4 or neck_center < 4:
        raise ValueError("no hay lugar para el escote")
    decs = max(1, min(round(neck_center * 0.2), (depth - 2) // 2, (neck_center - 2) // 2))
    return depth, decs, neck_center - 2 * decs


def neckband_stitches(neck_center: int, center_bo: int, depth: int) -> int:
    """Pts a levantar para la tira: espalda + centro + 3 de cada 4 hileras."""
    total = neck_center + center_bo + 2 * round(0.75 * depth)
    return total + total % 2


def neck_sections(before: int, after: int, decreases: int, rows: int, shoulder: int) -> tuple[Section, Section]:
    """Los dos hombros del escote redondo, cada uno tejido por separado.

    Primero los pts del final de la hilera de cierre (hombro derecho, con el
    escote al comienzo de las hileras del LD); despues los que quedaron en
    espera (hombro izquierdo).
    """
    sections = []
    for side_id, name, sts, at_start, intro in (
        ("neck_right", "section.neck_right", after, True, "pattern.note.neck_side_first"),
        ("neck_left", "section.neck_left", before, False, "pattern.note.neck_side_second"),
    ):
        steps = neck_side(sts, decreases, rows, neck_at_start=at_start)
        if steps[-1].stitch_count_end != shoulder:
            raise RuntimeError(f"{side_id}: termina con {steps[-1].stitch_count_end}, se esperaban {shoulder}")
        sections.append(
            Section(
                id=side_id,
                name_key=name,
                mode="flat",
                steps=tuple(steps),
                start_stitches=sts,
                end_stitches=shoulder,
                meta={"row_count": rows},
                bind_off=True,
                note_keys=(intro,),
            )
        )
    return sections[0], sections[1]
