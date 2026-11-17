"""Crochet: piezas planas, gorro, granny square y prendas en rectangulos.

El amigurumi (juguete en piezas) vive en engine/garments/toy.py. El granny
square es el clasico en redondo (grupos de 3 pa y esquinas de 2 cad); no
reproduce motivos complejos de la foto y lo declara en una advertencia.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from datetime import UTC, datetime
from math import pi

from engine import ENGINE_VERSION
from engine.distribution import split_even
from engine.gauge import Gauge, crochet_gauge
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
    StitchPatternName,
    resolve_gauge,
)
from engine.stitches.catalog import (
    adjust_stitches,
    catalog_id_for_name,
    expand_row,
    get_stitch,
    stitch_row_note,
)
from engine.stitches.kinds import StitchKind

_CROCHET_IDS = {"crochet_sc", "crochet_hdc", "crochet_dc", "crochet_tr"}
_KIND_BY_ID = {
    "crochet_sc": StitchKind.SC,
    "crochet_hdc": StitchKind.HDC,
    "crochet_dc": StitchKind.DC,
    "crochet_tr": StitchKind.TR,
}
# Puntos de crochet en hileras que se tejen en piezas rectangulares (bufanda,
# manta, bolso, prendas en rectangulos). El C2C tiene su propia geometria.
_ROW_IDS = {
    *_CROCHET_IDS,
    "crochet_ribbing",
    "granny_stitch",
    "crochet_linen",
    "v_stitch",
    "shell",
    "filet",
    "tunisian",
    "c2c",
}
# Piezas en redondo (gorro): un solo punto por vuelta; los puntos con grupos
# se reemplazan por el mas parecido de altura y se avisa.
_ROUND_FALLBACK = {
    "crochet_ribbing": "crochet_sc",
    "crochet_linen": "crochet_sc",
    "tunisian": "crochet_sc",
    "granny_stitch": "crochet_dc",
    "v_stitch": "crochet_dc",
    "shell": "crochet_dc",
    "filet": "crochet_dc",
    "c2c": "crochet_dc",
    "crochet_tr": "crochet_dc",  # 12 aumentos por vuelta: el pad da saltos de 9 cm
}


def _pattern_id(spec: GarmentSpec) -> str:
    pattern_id = catalog_id_for_name(spec.punto_base or StitchPatternName.CROCHET_SC)
    return pattern_id if pattern_id in _ROW_IDS else "crochet_sc"


def _stitch_notions(pattern_id: str, notions: tuple[str, ...]) -> tuple[str, ...]:
    if pattern_id == "tunisian":
        return tuple("notion.tunisian_hook" if n == "notion.crochet_hook" else n for n in notions)
    return notions


def _stitch_warnings(pattern_id: str) -> list[Warning]:
    """Avisos propios de algunos puntos (bordes, tecnica)."""
    if pattern_id in {"granny_stitch", "v_stitch", "shell", "filet", "crochet_linen"}:
        return [Warning("stitch_edges", "warning.stitch_edges", severity="info")]
    if pattern_id == "crochet_ribbing":
        return [Warning("ribbing_sideways", "warning.ribbing_sideways", severity="info")]
    if pattern_id == "tunisian":
        return [Warning("tunisian_curl", "warning.tunisian_curl", severity="info")]
    return []


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


def _flat_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str,
    tolerance_cm: float = 0.5,
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
            tolerance_cm=tolerance_cm,
            dimension="length",
        ),
        meta={"row_count": rows, "cast_on": stitches},
        bind_off=True,
    )


def _row_tolerance(gauge: Gauge) -> float:
    """Media hilera: lo maximo que se aleja el largo al redondear las hileras
    (con pad, una hilera mide mas de 1,5 cm)."""
    return max(0.5, 0.5 / gauge.rows_per_cm + 0.05)


def _width_tolerance(gauge: Gauge, multiple: int, base: float) -> float:
    """Ancho: el mas cercano con repeticiones enteras del punto (un abanico de
    6 pts mide ~5 cm) queda a lo sumo a media repeticion de la medida."""
    return max(base, gauge.cm_for_stitches(multiple + 1) / 2 + 0.05)


def _repeat_warning(actual: float, asked: float, base: float, lang: str, pattern_id: str) -> list[Warning]:
    """Aviso si las repeticiones enteras del punto alejan la medida."""
    if abs(actual - asked) <= base:
        return []
    from engine.i18n import t

    return [
        Warning(
            "stitch_repeat_width",
            "warning.stitch_repeat_width",
            params={
                "stitch": t(get_stitch(pattern_id).name_key, lang),
                "actual": f"{actual:.0f}",
                "asked": f"{asked:.0f}",
            },
        )
    ]


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
    # Elastico de crochet: se teje de costado (la cadena base da el largo y
    # las hileras, el ancho), asi las columnas de la hebra de atras quedan
    # verticales como un elastico.
    sideways = pattern_id == "crochet_ribbing"
    across, along = (length, width) if sideways else (width, length)
    stitches = adjust_stitches(
        max(1, round_half_up(across * gauge.stitches_per_cm)), multiple, mode="nearest"
    )
    rows = max(1, gauge.rows_for_cm(along))
    if pattern_id == "c2c":
        from engine.garments.c2c import c2c_section

        section = c2c_section(section_id, section_key, stitches, rows, along, max(1.5, _row_tolerance(gauge)))
    else:
        section = _flat_section(
            section_id,
            section_key,
            stitches,
            rows,
            pattern_id,
            along,
            note_key=stitch_row_note(pattern_id, "pattern.note.crochet_flat"),
            tolerance_cm=_row_tolerance(gauge),
        )
    across_cm, along_cm = gauge.cm_for_stitches(stitches), gauge.cm_for_rows(rows)
    width_cm, length_cm = (along_cm, across_cm) if sideways else (across_cm, along_cm)
    across_tol = _width_tolerance(gauge, multiple, 1.5)
    along_tol = max(1.5, _row_tolerance(gauge))
    width_tol, length_tol = (along_tol, across_tol) if sideways else (across_tol, along_tol)
    warnings = _warnings(params)
    if warning is not None:
        warnings.append(warning)
    warnings += _stitch_warnings(pattern_id)
    warnings += _repeat_warning(across_cm, across, 1.5, params.idioma, pattern_id)
    materials = _materials(
        spec,
        params,
        width * length,
        _stitch_notions(pattern_id, ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure")),
    )
    if pattern_id == "c2c":
        materials = _c2c_colors(spec, section, materials)
    return Pattern(
        meta=_meta(spec, params, family, title_key),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="width",
                value_cm=width_cm,
                target_cm=width,
                tolerance_cm=width_tol,
                kind="width",
            ),
            Measurement(
                key="length",
                value_cm=length_cm,
                target_cm=length,
                tolerance_cm=length_tol,
                kind="length",
            ),
        ),
        materials=materials,
        warnings=tuple(warnings),
    )


def _c2c_colors(spec: GarmentSpec, section: Section, materials: Materials) -> Materials:
    """C2C con dibujo de pixeles: metros por color segun los bloques de cada uno."""
    from engine.garments.c2c import c2c_chart

    chart = c2c_chart(spec, section.meta["c2c_width"], section.meta["c2c_height"])
    if chart is None:
        return materials
    total = chart.width * chart.height
    contrast = chart.contrast_cells()
    share = [(total - contrast) / total, contrast / total]
    colors = materials.colors[:2] if len(materials.colors) >= 2 else ("A", "B")
    meters = tuple(float(max(10, math.ceil(materials.meters * part / 10) * 10)) for part in share)
    return replace(materials, colors=colors, color_meters=meters)


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
    en prendas de crochet; ASUNCION). El C2C no se usa en prendas: pa."""
    if spec.punto_base is None:
        return "crochet_hdc"
    pattern_id = _pattern_id(spec)
    return "crochet_dc" if pattern_id == "c2c" else pattern_id


def _round_fallback(spec: GarmentSpec, params: PatternParams) -> list[Warning]:
    """Aviso si el punto de la foto no se puede tejer en redondo con aumentos."""
    pattern_id = _pattern_id(spec) if spec.punto_base is not None else "crochet_hdc"
    if pattern_id not in _ROUND_FALLBACK:
        return []
    from engine.i18n import t

    name = t(get_stitch(pattern_id).name_key, params.idioma)
    return [Warning("stitch_fallback_round", "warning.stitch_fallback_round", params={"stitch": name})]


def _circle_increase(gauge_spc: float, gauge_rpc: float) -> int:
    """Aumentos por vuelta de un circulo plano: 2 pi x alto de vuelta x pts/cm.

    Da los valores clasicos (6 en pb, 8 en mpa, 12 en pa)."""
    return max(6, min(12, round(2 * pi * gauge_spc / gauge_rpc)))


def generate_crochet_hat(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Gorro de crochet de arriba hacia abajo: circulo plano y tubo recto."""
    from engine.garments.accessories import HEAD_BY_SIZE

    stitch_id = _garment_stitch(spec)
    fallback = _round_fallback(spec, params)
    stitch_id = _ROUND_FALLBACK.get(stitch_id, stitch_id)
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
        warnings=tuple(_warnings(params) + fallback),
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
    # Los delanteros del cardigan son medio ancho: repeticiones enteras cada uno.
    half_multiple = 2 * multiple if kind == "cardigan" else multiple
    half = adjust_stitches(max(8, gauge.stitches_for_cm((size.bust_cm + ease) / 2)), half_multiple, mode="nearest")
    bust_tol = max(3.0, gauge.cm_for_stitches(half_multiple + 1) + 0.05)
    row_tol = _row_tolerance(gauge)
    rows = max(2, gauge.rows_for_cm(body_cm))
    # Par (hombros iguales), redondeado una sola vez: redondear a pts y despues
    # a par corria el cuello hasta 1,5 pts por lado (>3 cm en hilo grueso).
    neck_cm = max(24.0, size.neck_cm * 0.65)
    neck_open = min(half - 4, max(2, 2 * round_half_up(neck_cm * gauge.stitches_per_cm / 2)))
    shoulder = (half - neck_open) // 2
    sections = [_flat_section("back", "section.back", half, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat", tolerance_cm=row_tol)]
    sections[0] = replace(sections[0], meta={**sections[0].meta, "shoulder": shoulder})
    if kind == "cardigan":
        for side in ("left", "right"):
            sections.append(_flat_section(f"{side}_front", f"section.{side}_front", half // 2, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat", tolerance_cm=row_tol))
    else:
        sections.append(_flat_section("front", "section.front", half, rows, stitch_id, body_cm, note_key="pattern.note.crochet_flat", tolerance_cm=row_tol))
    measurements = [
        Measurement(key="bust", value_cm=gauge.cm_for_stitches(2 * half), target_cm=size.bust_cm + ease, tolerance_cm=bust_tol, kind="circumference"),
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
            sections.append(_flat_section(f"sleeve_{side}", f"section.sleeve_{side}", sleeve, sleeve_rows, stitch_id, sleeve_cm, note_key="pattern.note.crochet_flat", tolerance_cm=row_tol))
        measurements += [
            Measurement(key="sleeve_length", value_cm=gauge.cm_for_rows(sleeve_rows), target_cm=sleeve_cm, tolerance_cm=1.5, kind="length"),
            Measurement(key="upper_arm", value_cm=gauge.cm_for_stitches(sleeve), target_cm=size.upper_arm_cm + CROCHET_SLEEVE_EASE_CM, tolerance_cm=_width_tolerance(gauge, multiple, 3.0), kind="circumference"),
        ]
        area += 2 * gauge.cm_for_stitches(sleeve) * sleeve_cm
    warnings = _warnings(params)
    warnings.append(Warning("crochet_garment", "warning.crochet_garment"))
    warnings += _stitch_warnings(stitch_id)
    warnings += _repeat_warning(gauge.cm_for_stitches(2 * half), size.bust_cm + ease, 3.0, params.idioma, stitch_id)
    return Pattern(
        meta=_meta(spec_g, params, f"crochet_{kind}", f"title.{kind}_crochet"),
        spec=spec_g,
        params=params,
        sections=tuple(sections),
        measurements=tuple(measurements),
        materials=_materials(
            spec_g, params, area, _stitch_notions(stitch_id, ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure"))
        ),
        warnings=tuple(warnings),
        joins=tuple(joins),
    )
