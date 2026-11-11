"""Crochet: amigurumi y piezas planas.

Las formas de amigurumi se generan con anillo magico y aumentos/disminuciones
de 6 puntos por vuelta. El granny square es el clasico en redondo (grupos de
3 pa y esquinas de 2 cad); no reproduce motivos complejos de la foto y lo
declara en una advertencia.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from math import pi

from engine import ENGINE_VERSION
from engine.distribution import split_even
from engine.garments.base import ImpossibleProportionsError
from engine.gauge import crochet_gauge
from engine.ir import (
    CountRef,
    Item,
    JoinCheck,
    Materials,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import default_hook_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.spec import (
    GarmentSpec,
    PatternParams,
    Shape,
    StitchPatternName,
    Technique,
    resolve_gauge,
)
from engine.stitches.catalog import adjust_stitches, catalog_id_for_name, expand_row, get_stitch
from engine.stitches.kinds import StitchKind

_CROCHET_IDS = {"crochet_sc", "crochet_hdc", "crochet_dc"}
_KIND_BY_ID = {
    "crochet_sc": StitchKind.SC,
    "crochet_hdc": StitchKind.HDC,
    "crochet_dc": StitchKind.DC,
}


def _pattern_id(spec: GarmentSpec) -> str:
    pattern_id = catalog_id_for_name(spec.punto_base or StitchPatternName.CROCHET_SC)
    return pattern_id if pattern_id in _CROCHET_IDS else "crochet_sc"


def _with_crochet_gauge(spec: GarmentSpec, params: PatternParams) -> PatternParams:
    """Si no hay muestra medida, fija la referencia de crochet del punto base.

    Sin esto el motor usaba la densidad de dos agujas (22 x 30 en DK): 46
    hileras de pa daban "15 cm" cuando en realidad miden ~40 cm.
    """
    if params.densidad is not None:
        return params
    gauge = crochet_gauge(params.peso_hilo.value, _pattern_id(spec))
    return params.model_copy(update={"densidad": gauge})


def _kind(pattern_id: str) -> StitchKind:
    return _KIND_BY_ID[pattern_id]


def _meta(spec: GarmentSpec, params: PatternParams, family: str, title_key: str) -> PatternMeta:
    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json() + family).encode("utf-8")
    ).hexdigest()[:12]
    return PatternMeta(
        id=digest,
        family=family,
        title_key=title_key,
        size=params.talla,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )


def _materials(
    spec: GarmentSpec,
    params: PatternParams,
    area_cm2: float,
    notions: tuple[str, ...],
) -> Materials:
    meters, grams = estimate_yarn(area_cm2, params.peso_hilo)
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    return Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=None,
        hook_mm=params.ganchillo_mm or default_hook_mm(params.peso_hilo),
        meters=meters,
        grams=grams,
        notions=notions,
        colors=colors,
    )


def _warnings(params: PatternParams) -> list[Warning]:
    warnings = [
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("crochet_gauge", "warning.crochet_gauge", severity="info"),
    ]
    if params.medidas_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    return warnings


def _increase_round(
    stitches: int, increases: int, kind: StitchKind
) -> tuple[list[Item], int]:
    if increases < 0:
        raise ValueError("increases no puede ser negativo")
    if increases == 0:
        return ([Op(kind, times=stitches)] if stitches else []), stitches
    if stitches <= 0:
        raise ValueError("se necesitan puntos para aumentar")
    remaining = stitches - increases
    if remaining < 0:
        raise ValueError(
            f"no se pueden hacer {increases} aumentos en {stitches} puntos"
        )
    groups = split_even(remaining, increases)
    ops: list[Item] = []
    if len(set(groups)) == 1:  # reparto exacto: "(n pts, 1 aum) x veces"
        unit = ((Op(kind, times=groups[0]),) if groups[0] else ()) + (Op(StitchKind.CROCHET_INC),)
        return [Repeat(increases, unit)], stitches + increases
    for group in groups:
        if group:
            ops.append(Op(kind, times=group))
        ops.append(Op(StitchKind.CROCHET_INC))
    return ops, stitches + increases


def _decrease_round(
    stitches: int, decreases: int, kind: StitchKind
) -> tuple[list[Op], int]:
    if decreases < 0:
        raise ValueError("decreases no puede ser negativo")
    if decreases == 0:
        return ([Op(kind, times=stitches)] if stitches else []), stitches
    if decreases * 2 > stitches:
        raise ValueError(
            f"no se pueden hacer {decreases} disminuciones en {stitches} puntos"
        )
    remaining = stitches - 2 * decreases
    groups = split_even(remaining, decreases)
    ops: list[Op] = []
    for group in groups:
        if group:
            ops.append(Op(kind, times=group))
        ops.append(Op(StitchKind.CROCHET_DEC))
    return ops, stitches - decreases


def _amigurumi_shape(spec: GarmentSpec) -> str:
    if spec.forma is Shape.BOXY:
        return "cylinder"
    if spec.forma in {Shape.A_LINE, Shape.CURVED}:
        return "cone"
    return "sphere"


def generate_amigurumi(spec: GarmentSpec, params: PatternParams) -> Pattern:
    params = _with_crochet_gauge(spec, params)
    if spec.tecnica is not Technique.CROCHET:
        raise ImpossibleProportionsError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    gauge = resolve_gauge(params)
    diameter = params.dimensiones_cm.get("diameter", params.medidas_cm.get("diameter", 8.0))
    height = params.dimensiones_cm.get("height", params.medidas_cm.get("height", diameter))
    shape = _amigurumi_shape(spec)
    base_circumference = pi * diameter
    target = adjust_stitches(
        max(6, round_half_up(base_circumference * gauge.stitches_per_cm)),
        6,
        mode="nearest",
    )
    if abs(gauge.cm_for_stitches(target) - base_circumference) > 0.1 * base_circumference:
        raise ImpossibleProportionsError(
            "error.too_small_for_yarn",
            weight=params.peso_hilo.value,
            target=round(diameter, 1),
        )
    increase_rounds = (target - 6) // 6
    height_rows = max(1, gauge.rows_for_cm(height))
    if shape == "sphere":
        decrease_rounds = increase_rounds
        straight_rows = max(0, height_rows - increase_rounds - decrease_rounds)
    elif shape == "cylinder":
        decrease_rounds = 0
        straight_rows = max(1, height_rows - increase_rounds)
    else:
        decrease_rounds = 0
        straight_rows = max(0, height_rows - increase_rounds)

    pattern_id = _pattern_id(spec)
    kind = _kind(pattern_id)
    steps: list[Step] = [
        build_step(1, 0, (Op(StitchKind.MAGIC_RING),))
    ]
    current = 6
    number = 2
    for _ in range(increase_rounds):
        before = current
        items, current = _increase_round(current, 6, kind)
        steps.append(
            build_step(number, before, items, note_key="pattern.note.amigurumi_increase")
        )
        number += 1
    for _ in range(straight_rows):
        steps.append(
            build_step(number, current, (Op(kind, times=current),), note_key="pattern.note.plain")
        )
        number += 1
    for _ in range(decrease_rounds):
        dec_items, current = _decrease_round(current, 6, kind)
        steps.append(
            build_step(number, current + 6, dec_items, note_key="pattern.note.amigurumi_decrease")
        )
        number += 1
    if shape == "sphere" and current != 6:
        raise RuntimeError(f"amigurumi: termina con {current} puntos, se esperaban 6")

    total_rows = len(steps)
    actual_height = gauge.cm_for_rows(total_rows)
    if abs(actual_height - height) > 1.5:
        raise ImpossibleProportionsError(
            "error.too_small_for_yarn",
            weight=params.peso_hilo.value,
            target=round(height, 1),
        )
    target_circumference = gauge.cm_for_stitches(target)
    actual_diameter = target_circumference / pi
    section = Section(
        id="amigurumi",
        name_key="section.amigurumi",
        mode="round",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=current,
        target=(
            None
            if shape == "sphere"
            else SectionTarget(
                measurement_key="circumference",
                target_cm=base_circumference,
                tolerance_cm=2.5,
                dimension="circumference",
            )
        ),
        meta={"row_count": total_rows, "base_stitches": target},
        bind_off=True,
    )
    area = (
        4.0 * pi * (diameter / 2.0) ** 2
        if shape == "sphere"
        else pi * diameter * height
    )
    warnings = _warnings(params)
    warnings.append(
        Warning("amigurumi_approx", "warning.amigurumi_approx", severity="warning")
    )
    return Pattern(
        meta=_meta(spec, params, "amigurumi", "title.amigurumi"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="diameter",
                value_cm=actual_diameter,
                target_cm=diameter,
                tolerance_cm=1.5,
                kind="circumference",
            ),
            Measurement(
                key="height",
                value_cm=actual_height,
                target_cm=height,
                tolerance_cm=1.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            area,
            ("notion.crochet_hook", "notion.stitch_markers", "notion.tapestry_needle"),
        ),
        warnings=tuple(warnings),
    )


def _flat_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str,
) -> Section:
    pattern = get_stitch(pattern_id)
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CH, times=stitches),),
            note_key="pattern.note.crochet_foundation",
        )
    ]
    for number in range(2, rows + 2):
        steps.append(
            build_step(
                number,
                stitches,
                expand_row(pattern, stitches, number - 1),
                note_key=note_key if number == 2 else None,
            )
        )
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=stitches,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=target_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": rows, "cast_on": stitches},
        bind_off=True,
    )


def _flat_pattern(
    spec: GarmentSpec,
    params: PatternParams,
    *,
    family: str,
    title_key: str,
    section_id: str,
    section_key: str,
    width: float,
    length: float,
    warning: Warning | None = None,
) -> Pattern:
    params = _with_crochet_gauge(spec, params)
    gauge = resolve_gauge(params)
    pattern_id = _pattern_id(spec)
    multiple = get_stitch(pattern_id).multiple
    stitches = adjust_stitches(
        max(1, round_half_up(width * gauge.stitches_per_cm)), multiple, mode="nearest"
    )
    rows = max(1, gauge.rows_for_cm(length))
    section = _flat_section(
        section_id,
        section_key,
        stitches,
        rows,
        pattern_id,
        length,
        note_key="pattern.note.crochet_flat",
    )
    warnings = _warnings(params)
    if warning is not None:
        warnings.append(warning)
    return Pattern(
        meta=_meta(spec, params, family, title_key),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="width",
                value_cm=gauge.cm_for_stitches(stitches),
                target_cm=width,
                tolerance_cm=1.5,
                kind="width",
            ),
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(rows),
                target_cm=length,
                tolerance_cm=1.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            width * length,
            ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )


def generate_crochet_flat_piece(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 20.0))
    height = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 20.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_flat_piece",
        title_key="title.flat_piece",
        section_id="flat_piece",
        section_key="section.flat_piece",
        width=width,
        length=height,
        warning=Warning("flat_piece", "warning.flat_piece"),
    )


def generate_crochet_bag(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 30.0))
    height = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 30.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_bag",
        title_key="title.bag",
        section_id="bag",
        section_key="section.bag",
        width=width,
        length=height,
        warning=Warning("bag_flat", "warning.bag_flat"),
    )


def generate_crochet_scarf(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 25.0))
    length = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 180.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_scarf",
        title_key="title.scarf",
        section_id="scarf",
        section_key="section.scarf",
        width=width,
        length=length,
    )


def granny_round_stitches(round_number: int) -> int:
    """Puntos (pa + cad) de la vuelta n de un granny clasico: 16n + 4."""
    return 16 * round_number + 4


def _granny_rounds(rounds: int) -> tuple[Step, ...]:
    steps: list[Step] = [
        build_step(1, 0, (Repeat(4, (Op(StitchKind.GRANNY_START),)),))
    ]
    for number in range(2, rounds + 1):
        sides = number - 2
        group: tuple[Op, ...] = (Op(StitchKind.GRANNY_CORNER),)
        if sides:
            group += (Op(StitchKind.GRANNY_SIDE, times=sides),)
        steps.append(
            build_step(number, granny_round_stitches(number - 1), (Repeat(4, group),))
        )
    return tuple(steps)


def generate_granny_square(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Granny square clasico en redondo: grupos de 3 pa, esquinas de 2 cad.

    Lado = 2 x vueltas x alto de una vuelta de pa (ASUNCION: el anillo central
    queda absorbido en la primera vuelta). Ver docs/fuentes.md.
    """
    if params.densidad is None:
        params = params.model_copy(
            update={"densidad": crochet_gauge(params.peso_hilo.value, "crochet_dc")}
        )
    gauge = resolve_gauge(params)
    size = params.dimensiones_cm.get("size", params.medidas_cm.get("size", 15.0))
    round_cm = 1.0 / gauge.rows_per_cm
    rounds = max(1, round_half_up(size / (2 * round_cm)))
    actual = 2 * rounds * round_cm
    steps = _granny_rounds(rounds)
    section = Section(
        id="granny_square",
        name_key="section.granny_square",
        mode="round",
        steps=steps,
        start_stitches=0,
        end_stitches=granny_round_stitches(rounds),
        target=SectionTarget(
            measurement_key="width",
            target_cm=size,
            tolerance_cm=round_cm,
            dimension="length",
        ),
        # Cada vuelta suma alto en los dos lados del cuadrado.
        meta={"row_count": 2 * rounds, "rounds": rounds},
        bind_off=True,
        note_keys=("pattern.granny_intro",),
    )
    warnings = _warnings(params)
    warnings.append(Warning("granny_classic", "warning.granny_classic"))
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    if len(colors) > 1:
        letters = ", ".join(f"{chr(65 + i)} ({c})" for i, c in enumerate(colors))
        warnings.append(
            Warning(
                "granny_colors",
                "pattern.granny_colors",
                severity="info",
                params={"colors": letters},
            )
        )
    return Pattern(
        meta=_meta(spec, params, "granny_square", "title.granny_square"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            # Tolerancia: media vuelta por lado es el error maximo de redondeo.
            Measurement(
                key="width", value_cm=actual, target_cm=size, tolerance_cm=round_cm, kind="width"
            ),
            Measurement(
                key="length", value_cm=actual, target_cm=size, tolerance_cm=round_cm, kind="length"
            ),
        ),
        materials=_materials(
            spec,
            params,
            actual * actual,
            ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Gorro, cuello y chal de crochet; prendas de crochet en rectangulos.
# ---------------------------------------------------------------------------


def _garment_stitch(spec: GarmentSpec) -> str:
    """Punto base de prendas: el de la foto, o medio punto alto (el mas usado
    en prendas de crochet; ASUNCION)."""
    if spec.punto_base is None:
        return "crochet_hdc"
    return _pattern_id(spec)


def _circle_increase(gauge_spc: float, gauge_rpc: float) -> int:
    """Aumentos por vuelta de un circulo plano: 2 pi x alto de vuelta x pts/cm.

    Da los valores clasicos (6 en pb, 8 en mpa, 12 en pa)."""
    return max(6, min(12, round(2 * pi * gauge_spc / gauge_rpc)))


def generate_crochet_hat(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Gorro de crochet de arriba hacia abajo: circulo plano y tubo recto."""
    from engine.garments.accessories import HEAD_BY_SIZE

    stitch_id = _garment_stitch(spec)
    spec_hat = spec.model_copy(update={"punto_base": StitchPatternName(stitch_id)})
    params = _with_crochet_gauge(spec_hat, params)
    gauge = resolve_gauge(params)
    kind = _kind(stitch_id)
    head = params.dimensiones_cm.get("head", params.medidas_cm.get("head", HEAD_BY_SIZE.get(params.talla.upper(), 56.0)))
    height = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 21.0))
    circumference = head * 0.92  # ASUNCION: el crochet cede menos que el tejido
    inc = _circle_increase(gauge.stitches_per_cm, gauge.rows_per_cm)
    target = adjust_stitches(max(inc, round_half_up(circumference * gauge.stitches_per_cm)), inc, mode="nearest")
    crown = target // inc
    rows = max(crown + 1, gauge.rows_for_cm(height))
    steps: list[Step] = [build_step(1, 0, (Op(StitchKind.RING, width=inc),))]
    current = inc
    for number in range(2, rows + 1):
        if current < target:
            items, current = _increase_round(current, inc, kind)
            note = "pattern.note.crochet_crown" if number == 2 else "pattern.note.circle_increase"
            steps.append(build_step(number, current - inc, items, note_key=note))
        else:
            steps.append(build_step(number, current, (Op(kind, times=current),), note_key="pattern.note.plain" if steps[-1].note_key != "pattern.note.plain" else None))
    section = Section(
        id="hat",
        name_key="section.hat_crochet",
        mode="round",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=current,
        target=SectionTarget(measurement_key="length", target_cm=height, tolerance_cm=1.5, dimension="length"),
        meta={"row_count": rows},
        bind_off=True,
    )
    return Pattern(
        meta=_meta(spec_hat, params, "crochet_hat", "title.hat_crochet"),
        spec=spec_hat,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(key="circumference", value_cm=gauge.cm_for_stitches(current), target_cm=circumference, tolerance_cm=2.5, kind="circumference"),
            Measurement(key="length", value_cm=gauge.cm_for_rows(rows), target_cm=height, tolerance_cm=1.5, kind="length"),
        ),
        materials=_materials(spec_hat, params, circumference * height, ("notion.crochet_hook", "notion.stitch_markers", "notion.tapestry_needle")),
        warnings=tuple(_warnings(params)),
    )


def generate_crochet_cowl(spec: GarmentSpec, params: PatternParams) -> Pattern:
    circumference = params.dimensiones_cm.get("circumference", params.medidas_cm.get("circumference", 60.0))
    length = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 25.0))
    return _flat_pattern(
        spec, params, family="crochet_cowl", title_key="title.cowl_crochet", section_id="cowl",
        section_key="section.cowl", width=circumference, length=length,
        warning=Warning("cowl_seam", "warning.cowl_seam", severity="info"),
    )


def generate_crochet_shawl(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 50.0))
    length = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 170.0))
    return _flat_pattern(
        spec, params, family="crochet_shawl", title_key="title.shawl_crochet", section_id="shawl",
        section_key="section.shawl", width=width, length=length,
        warning=Warning("shawl_rectangular", "warning.shawl_rectangular"),
    )


CROCHET_SLEEVE_EASE_CM = 6.0


def generate_crochet_garment(spec: GarmentSpec, params: PatternParams, kind: str) -> Pattern:
    """Pullover, cardigan o chaleco de crochet en rectangulos que se cosen.

    Es la construccion de crochet mas comun para principiantes (hombro caido,
    mangas rectas, cuello barco al coser los hombros). ASUNCION: abertura del
    cuello = 65 % del contorno de cuello, minimo 24 cm. Ver docs/fuentes.md.
    """
    from engine.garments.flat import _body_length_cm, _sleeve_length_cm
    from engine.sizes import ease_for_fit, resolve_body_size

    stitch_id = _garment_stitch(spec)
    spec_g = spec.model_copy(update={"punto_base": StitchPatternName(stitch_id)})
    params = _with_crochet_gauge(spec_g, params)
    gauge = resolve_gauge(params)
    size = resolve_body_size(params.talla, params.medidas_cm)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    multiple = get_stitch(stitch_id).multiple
    body_cm = _body_length_cm(spec, size)
    half = adjust_stitches(max(8, gauge.stitches_for_cm((size.bust_cm + ease) / 2)), 2 * multiple, mode="nearest")
    rows = max(2, gauge.rows_for_cm(body_cm))
    neck_open = min(half - 4, adjust_stitches(gauge.stitches_for_cm(max(24.0, size.neck_cm * 0.65)), 2, mode="nearest"))
    shoulder = (half - neck_open) // 2
    sections = [_flat_section("back", "section.back", half, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat")]
    sections[0] = replace(sections[0], meta={**sections[0].meta, "shoulder": shoulder})
    if kind == "cardigan":
        for side in ("left", "right"):
            sections.append(_flat_section(f"{side}_front", f"section.{side}_front", half // 2, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat"))
    else:
        sections.append(_flat_section("front", "section.front", half, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat"))
    measurements = [
        Measurement(key="bust", value_cm=gauge.cm_for_stitches(2 * half), target_cm=size.bust_cm + ease, tolerance_cm=3.0, kind="circumference"),
        Measurement(key="body_length", value_cm=gauge.cm_for_rows(rows), target_cm=body_cm, tolerance_cm=1.5, kind="length"),
        Measurement(key="neck", value_cm=2 * gauge.cm_for_stitches(neck_open), target_cm=2 * max(24.0, size.neck_cm * 0.65), tolerance_cm=3.0, kind="circumference"),
    ]
    joins = [
        JoinCheck(
            label_key="join.side_seam",
            left=(CountRef("back", "end"),),
            right=tuple(CountRef(s.id, "end") for s in sections[1:]),
        )
    ]
    area = gauge.cm_for_stitches(2 * half) * body_cm
    if kind != "vest":
        sleeve_cm = _sleeve_length_cm(spec, size)
        sleeve = adjust_stitches(max(8, gauge.stitches_for_cm(size.upper_arm_cm + CROCHET_SLEEVE_EASE_CM)), multiple, mode="nearest")
        sleeve_rows = max(2, gauge.rows_for_cm(sleeve_cm))
        for side in ("left", "right"):
            sections.append(_flat_section(f"sleeve_{side}", f"section.sleeve_{side}", sleeve, sleeve_rows, stitch_id, sleeve_cm, note_key="pattern.note.crochet_flat"))
        measurements += [
            Measurement(key="sleeve_length", value_cm=gauge.cm_for_rows(sleeve_rows), target_cm=sleeve_cm, tolerance_cm=1.5, kind="length"),
            Measurement(key="upper_arm", value_cm=gauge.cm_for_stitches(sleeve), target_cm=size.upper_arm_cm + CROCHET_SLEEVE_EASE_CM, tolerance_cm=3.0, kind="circumference"),
        ]
        area += 2 * gauge.cm_for_stitches(sleeve) * sleeve_cm
    warnings = _warnings(params)
    warnings.append(Warning("crochet_garment", "warning.crochet_garment"))
    return Pattern(
        meta=_meta(spec_g, params, f"crochet_{kind}", f"title.{kind}_crochet"),
        spec=spec_g,
        params=params,
        sections=tuple(sections),
        measurements=tuple(measurements),
        materials=_materials(spec_g, params, area, ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure")),
        warnings=tuple(warnings),
        joins=tuple(joins),
    )
