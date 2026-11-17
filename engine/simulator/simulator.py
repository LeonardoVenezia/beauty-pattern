"""Verificador determinista de patrones.

Interpreta la IR final vuelta por vuelta y comprueba:
- que cada vuelta consuma exactamente los puntos disponibles;
- que el conteo declarado coincida con el calculado;
- que los aumentos y disminuciones coincidan con lo declarado por seccion;
- que las medidas finales coincidan con los objetivos dentro de tolerancia;
- que las uniones tengan el mismo conteo de ambos lados.

Si algo falla, el patron NO se entrega.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from engine.ir import Pattern, Section, Step
from engine.spec import resolve_gauge
from engine.stitches.kinds import StitchKind

_INCREASE_KINDS = {
    StitchKind.M1L,
    StitchKind.M1R,
    StitchKind.KFB,
    StitchKind.YO,
    StitchKind.CH,
    StitchKind.CROCHET_INC,
    StitchKind.MAGIC_RING,
}
_DECREASE_KINDS = {
    StitchKind.K2TOG,
    StitchKind.SSK,
    StitchKind.P2TOG,
    StitchKind.SSP,
    StitchKind.CROCHET_DEC,
}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    section: str | None = None
    step: int | None = None
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class SimulationReport:
    ok: bool
    issues: tuple[Issue, ...]
    sections_checked: int
    steps_checked: int
    final_counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    def raise_if_failed(self) -> None:
        if not self.ok:
            detail = "; ".join(issue.message for issue in self.errors)
            raise SimulationError(detail)


class SimulationError(Exception):
    """El patron no paso la verificacion."""


def _step_increases(step: Step) -> int:
    total = 0
    for op in step.expanded_ops():
        if op.kind in _INCREASE_KINDS:
            total += max(0, op.produces - op.consumes)
    return total


def _step_decreases(step: Step) -> int:
    total = 0
    for op in step.expanded_ops():
        if op.kind in _DECREASE_KINDS:
            total += max(0, op.consumes - op.produces)
    return total


def _check_section(
    section: Section,
    gauge_sts: float,
    gauge_rows: float,
    issues: list[Issue],
) -> int:
    available = section.start_stitches
    total_increases = 0
    total_decreases = 0
    previous_number = -1
    for step in section.steps:
        if step.number <= previous_number:
            issues.append(
                Issue(
                    code="step_order",
                    message=(
                        f"seccion {section.id}: la vuelta {step.number} no es "
                        f"posterior a {previous_number}"
                    ),
                    section=section.id,
                    step=step.number,
                )
            )
        previous_number = step.number
        consumed = step.consumes
        produced = step.produces
        if consumed != available:
            issues.append(
                Issue(
                    code="row_consumption",
                    message=(
                        f"seccion {section.id}, vuelta {step.number}: consume "
                        f"{consumed} puntos pero hay {available} disponibles"
                    ),
                    section=section.id,
                    step=step.number,
                )
            )
        computed_end = available - consumed + produced
        if step.stitch_count_end != computed_end:
            issues.append(
                Issue(
                    code="declared_count",
                    message=(
                        f"seccion {section.id}, vuelta {step.number}: declara "
                        f"{step.stitch_count_end} puntos pero el calculo da "
                        f"{computed_end}"
                    ),
                    section=section.id,
                    step=step.number,
                )
            )
        # Vuelta de un grafico de colores: la repeticion tiene que entrar un
        # numero entero de veces y la vuelta no puede dar forma.
        repeat = dict(step.note_params).get("chart_repeat")
        if repeat is not None and (
            int(repeat) <= 0 or consumed % int(repeat) != 0 or produced != consumed
        ):
            issues.append(
                Issue(
                    code="chart_repeat",
                    message=(
                        f"seccion {section.id}, vuelta {step.number}: la repeticion "
                        f"de {repeat} pts del grafico no entra justa en {consumed} pts "
                        "o la vuelta cambia el conteo"
                    ),
                    section=section.id,
                    step=step.number,
                )
            )
        # Tunecino: cada hilera son dos pasadas. La de ida levanta los lazos y
        # la de vuelta los cierra; sin la vuelta, la hilera no esta terminada.
        ops = step.expanded_ops()
        if any(op.kind is StitchKind.TSS for op in ops) and (
            ops[-1].kind is not StitchKind.TUNISIAN_RETURN
            or sum(op.kind is StitchKind.TUNISIAN_RETURN for op in ops) != 1
        ):
            issues.append(
                Issue(
                    code="tunisian_return",
                    message=(
                        f"seccion {section.id}, vuelta {step.number}: la pasada de ida "
                        "del tunecino no termina con una sola pasada de vuelta"
                    ),
                    section=section.id,
                    step=step.number,
                )
            )
        total_increases += _step_increases(step)
        total_decreases += _step_decreases(step)
        available = computed_end

    if available != section.end_stitches:
        issues.append(
            Issue(
                code="section_end",
                message=(
                    f"seccion {section.id}: termina con {available} puntos pero "
                    f"declara {section.end_stitches}"
                ),
                section=section.id,
            )
        )
    if not section.steps and section.start_stitches != section.end_stitches:
        issues.append(
            Issue(
                code="empty_section",
                message=f"seccion {section.id}: sin vueltas pero cambia de conteo",
                section=section.id,
            )
        )

    expected_increases = section.meta.get("expected_increases")
    if expected_increases is not None and total_increases != expected_increases:
        issues.append(
            Issue(
                code="increase_sum",
                message=(
                    f"seccion {section.id}: {total_increases} aumentos, se "
                    f"esperaban {expected_increases}"
                ),
                section=section.id,
            )
        )
    expected_decreases = section.meta.get("expected_decreases")
    if expected_decreases is not None and total_decreases != expected_decreases:
        issues.append(
            Issue(
                code="decrease_sum",
                message=(
                    f"seccion {section.id}: {total_decreases} disminuciones, se "
                    f"esperaban {expected_decreases}"
                ),
                section=section.id,
            )
        )

    if section.target is not None:
        target = section.target
        if target.dimension == "length":
            rows = section.meta.get("row_count", len(section.steps))
            actual_cm = rows / gauge_rows
        else:
            actual_cm = section.end_stitches / gauge_sts
        if abs(actual_cm - target.target_cm) > target.tolerance_cm + 1e-9:
            issues.append(
                Issue(
                    code="section_measurement",
                    message=(
                        f"seccion {section.id}: {target.measurement_key} = "
                        f"{actual_cm:.1f} cm, objetivo {target.target_cm:.1f} cm "
                        f"(tolerancia {target.tolerance_cm:.1f})"
                    ),
                    section=section.id,
                )
            )
    return available


_CORNERS = {
    StitchKind.CORNER_SC,
    StitchKind.CORNER_DC,
    StitchKind.SQUARE_TURN,
    StitchKind.GRANNY_CORNER,
    StitchKind.HEX_CORNER,
    StitchKind.HEX_CORNER_SC,
}
# Piezas que se tejen iguales: mismo conteo en cada vuelta.
_PAIRS = (("sleeve_left", "sleeve_right"), ("cuff_left", "cuff_right"), ("button_band_left", "button_band_right"))
# Piezas en espejo tejidas en plano: los cierres van al principio de una hilera
# de su lado, asi que una pieza puede ir UNA hilera corrida respecto de la
# otra (es lo habitual en patrones publicados), nunca mas, y terminan iguales.
_MIRRORS = (("left_front", "right_front"), ("front_left", "front_right"), ("neck_left", "neck_right"))


def _mirrored(a: list[int], b: list[int]) -> bool:
    if len(a) != len(b) or a[-1:] != b[-1:]:
        return False
    return all(y in a[max(0, i - 1) : i + 2] for i, y in enumerate(b)) and all(
        x in b[max(0, i - 1) : i + 2] for i, x in enumerate(a)
    )


def _check_symmetry(pattern: Pattern, issues: list[Issue]) -> None:
    """Coherencia geometrica, no solo aritmetica: un cuadrado tiene sus 4
    lados iguales en cada vuelta y las piezas pares son identicas. Una vuelta
    puede cerrar la cuenta y aun asi tener 10 pts de un lado y 11 del otro."""
    for section in pattern.sections:
        for step in section.steps:
            ops = list(step.expanded_ops())
            corners = [i for i, op in enumerate(ops) if op.kind in _CORNERS]
            if len(corners) not in (4, 6):  # cuadrado o hexagono
                continue
            ends = [*corners[1:], corners[0] + len(ops)]
            sides = [
                sum(ops[k % len(ops)].produces for k in range(a + 1, b)) for a, b in zip(corners, ends, strict=True)
            ]
            if len(set(sides)) > 1:
                issues.append(
                    Issue(
                        code="square_sides",
                        message=f"vuelta {step.number}: lados desiguales {sides}",
                        section=section.id,
                        step=step.number,
                    )
                )
    by_id = {section.id: section for section in pattern.sections}
    for left, right in (*_PAIRS, *_MIRRORS):
        a, b = by_id.get(left), by_id.get(right)
        if a is None or b is None:
            continue
        counts_a = [st.stitch_count_end for st in a.steps]
        counts_b = [st.stitch_count_end for st in b.steps]
        if counts_a != counts_b and not ((left, right) in _MIRRORS and _mirrored(counts_a, counts_b)):
            issues.append(
                Issue(code="pair_mismatch", message=f"{left} y {right} no tienen los mismos conteos", section=right)
            )


def simulate(pattern: Pattern) -> SimulationReport:
    issues: list[Issue] = []
    gauge = resolve_gauge(pattern.params)
    gauge_sts = gauge.stitches_per_cm
    gauge_rows = gauge.rows_per_cm

    seen_ids: set[str] = set()
    for section in pattern.sections:
        if section.id in seen_ids:
            issues.append(
                Issue(
                    code="duplicate_section",
                    message=f"seccion duplicada: {section.id}",
                    section=section.id,
                )
            )
        seen_ids.add(section.id)
    if not pattern.sections:
        issues.append(Issue(code="no_sections", message="el patron no tiene secciones"))

    final_counts: dict[str, int] = {}
    steps_checked = 0
    for section in pattern.sections:
        final_counts[section.id] = _check_section(
            section, gauge_sts, gauge_rows, issues
        )
        steps_checked += len(section.steps)
    _check_symmetry(pattern, issues)

    for measurement in pattern.measurements:
        if measurement.target_cm is None:
            continue
        if abs(measurement.value_cm - measurement.target_cm) > (
            measurement.tolerance_cm + 1e-9
        ):
            issues.append(
                Issue(
                    code="measurement",
                    message=(
                        f"medida {measurement.key}: {measurement.value_cm:.1f} cm, "
                        f"objetivo {measurement.target_cm:.1f} cm (tolerancia "
                        f"{measurement.tolerance_cm:.1f})"
                    ),
                )
            )

    sections_by_id = {section.id: section for section in pattern.sections}
    for join in pattern.joins:
        left = 0
        right = 0
        failed = False
        for ref in join.left:
            joined = sections_by_id.get(ref.section)
            if joined is None:
                issues.append(
                    Issue(
                        code="join_section",
                        message=f"union {join.label_key}: falta {ref.section}",
                    )
                )
                failed = True
                continue
            try:
                left += joined.count_for(ref.field)
            except (KeyError, ValueError) as exc:
                issues.append(
                    Issue(
                        code="join_field",
                        message=f"union {join.label_key}: {exc}",
                    )
                )
                failed = True
        for ref in join.right:
            joined = sections_by_id.get(ref.section)
            if joined is None:
                issues.append(
                    Issue(
                        code="join_section",
                        message=f"union {join.label_key}: falta {ref.section}",
                    )
                )
                failed = True
                continue
            try:
                right += joined.count_for(ref.field)
            except (KeyError, ValueError) as exc:
                issues.append(
                    Issue(
                        code="join_field",
                        message=f"union {join.label_key}: {exc}",
                    )
                )
                failed = True
        if not failed and left != right:
            issues.append(
                Issue(
                    code="join_mismatch",
                    message=(
                        f"union {join.label_key}: {left} puntos de un lado, "
                        f"{right} del otro"
                    ),
                )
            )

    errors = [issue for issue in issues if issue.severity == "error"]
    return SimulationReport(
        ok=not errors,
        issues=tuple(issues),
        sections_checked=len(pattern.sections),
        steps_checked=steps_checked,
        final_counts=final_counts,
    )
