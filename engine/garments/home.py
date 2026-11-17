"""Hogar, al crochet y a dos agujas: piezas planas (posavasos, individual,
agarradera, pano, carpeta), fundas (mate, termo, taza, botella; celular,
anteojos, cartuchera, notebook), canastos, almohadones y alfombras.

Casi todo sale de tres geometrias (docs/investigacion-2026-11.md):
- disco o rectangulo plano (circulo de crochet con aumentos por vuelta,
  ovalo alrededor de una cadena, rectangulo en hileras; en agujas, circulo
  desde el centro y rectangulo en punto bobo);
- funda: base + tubo (base redonda y paredes rectas que abrazan el objeto) o
  bolsita plana (dos caras y fondo);
- canasto: base (redonda, ovalada o rectangular) + paredes firmes.

Las medidas por defecto de cada objeto y las holguras son ASUNCIONES
documentadas en docs/fuentes.md; la persona puede pasar las suyas en
`PatternParams.dimensiones_cm`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import lcm, pi
from typing import Literal

from engine import ENGINE_VERSION
from engine.garments.base import ImpossibleProportionsError
from engine.garments.home_shapes import (
    KNIT_SECTORS,
    change_items,
    circle_increase,
    crochet_circle,
    crochet_oval,
    handle_round,
    knit_circle,
    plain_rounds,
    spread,
)
from engine.garments.toy import CROCHET_TIGHTNESS, KNIT_TIGHTNESS, TOY_HOOK_MM, TOY_NEEDLE_MM
from engine.gauge import DEFAULT_GAUGES, Gauge, crochet_gauge
from engine.ir import (
    CountRef,
    Item,
    JoinCheck,
    Materials,
    Measurement,
    Note,
    Op,
    Pattern,
    PatternMeta,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import default_hook_mm, default_needle_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.spec import (
    CozyItem,
    FlatItem,
    FlatShape,
    GarmentSpec,
    MotifShape,
    PatternParams,
    Technique,
)
from engine.stitches.catalog import adjust_stitches, catalog_id_for_name, expand_row, get_stitch
from engine.stitches.kinds import StitchKind

Craft = Literal["crochet", "knit"]

_CROCHET_KINDS = {
    "crochet_sc": StitchKind.SC,
    "crochet_hdc": StitchKind.HDC,
    "crochet_dc": StitchKind.DC,
}

# ---------------------------------------------------------------------------
# Medidas por defecto (ASUNCION: docs/fuentes.md, "Hogar").
# ---------------------------------------------------------------------------

Dims = tuple[float, float]  # (ancho, largo) en cm; circulo: (diametro, diametro)

FLAT_ITEMS: dict[FlatItem, tuple[FlatShape, dict[FlatShape, Dims]]] = {
    FlatItem.COASTER: (
        FlatShape.CIRCLE,
        {FlatShape.CIRCLE: (10, 10), FlatShape.SQUARE: (10, 10), FlatShape.RECTANGLE: (12, 9), FlatShape.OVAL: (12, 9)},
    ),
    FlatItem.PLACEMAT: (
        FlatShape.RECTANGLE,
        {FlatShape.CIRCLE: (35, 35), FlatShape.SQUARE: (35, 35), FlatShape.RECTANGLE: (45, 32), FlatShape.OVAL: (45, 32)},
    ),
    FlatItem.POTHOLDER: (
        FlatShape.SQUARE,
        {FlatShape.CIRCLE: (20, 20), FlatShape.SQUARE: (20, 20), FlatShape.RECTANGLE: (22, 18), FlatShape.OVAL: (22, 18)},
    ),
    FlatItem.DISHCLOTH: (
        FlatShape.SQUARE,
        {FlatShape.CIRCLE: (25, 25), FlatShape.SQUARE: (25, 25), FlatShape.RECTANGLE: (30, 22), FlatShape.OVAL: (30, 22)},
    ),
    FlatItem.DOILY: (
        FlatShape.CIRCLE,
        {FlatShape.CIRCLE: (30, 30), FlatShape.SQUARE: (30, 30), FlatShape.RECTANGLE: (40, 30), FlatShape.OVAL: (40, 28)},
    ),
}
# Punto de crochet por objeto si la foto no dice otro: pb para lo firme
# (posavasos, agarradera), mpa para lo rapido, pa para la carpetita.
FLAT_CROCHET_STITCH: dict[FlatItem, str] = {
    FlatItem.COASTER: "crochet_sc",
    FlatItem.PLACEMAT: "crochet_hdc",
    FlatItem.POTHOLDER: "crochet_sc",
    FlatItem.DISHCLOTH: "crochet_hdc",
    FlatItem.DOILY: "crochet_dc",
}
RUG_SIZES: dict[FlatShape, Dims] = {
    FlatShape.CIRCLE: (60, 60),
    FlatShape.SQUARE: (60, 60),
    FlatShape.RECTANGLE: (90, 60),
    FlatShape.OVAL: (90, 60),
}
PILLOW_SIZES: dict[FlatShape, Dims] = {  # medida del relleno
    FlatShape.CIRCLE: (40, 40),
    FlatShape.SQUARE: (40, 40),
    FlatShape.RECTANGLE: (50, 30),
    FlatShape.OVAL: (50, 30),
}
PILLOW_NEGATIVE_EASE_CM = 2.0  # la funda, 2 cm menos que el relleno: queda mullida
PILLOW_BACK_SHARE = 0.6  # cada mitad del sobre cubre el 60 %: se superponen 20 %
PILLOW_BAND_CM = 3.0
BASKET_SIZES: dict[FlatShape, Dims] = {
    FlatShape.CIRCLE: (20, 20),
    FlatShape.SQUARE: (20, 20),
    FlatShape.RECTANGLE: (25, 18),
    FlatShape.OVAL: (25, 18),
}
BASKET_HEIGHT_CM = 15.0
HANDLE_MIN_HEIGHT_CM = 12.0  # canastos mas bajos: sin asas
HANDLE_WIDTH_CM = 8.0  # entra una mano
HANDLE_FROM_TOP_CM = 2.5

# Objetos redondos: (diametro, alto a cubrir, diametro de la boca o None,
# correa en cm o 0). Mate de calabaza o camionero: panza ~8 cm, ~9 cm de
# alto, boca ~6,5 cm; termo de 1 l: ~9 cm, cuerpo hasta el hombro ~25 cm.
COZY_ROUND: dict[CozyItem, tuple[float, float, float | None, float]] = {
    CozyItem.MATE: (8.0, 9.0, 6.5, 0.0),
    CozyItem.THERMOS: (9.0, 25.0, None, 100.0),
    CozyItem.CUP: (8.0, 9.5, None, 0.0),
    CozyItem.BOTTLE: (7.0, 18.0, None, 0.0),
}
COZY_EASE = {"crochet": -0.05, "knit": -0.10}  # contorno: la funda abraza
MATE_SHAPING_SHARE = 0.3  # el tercio de arriba se cierra hacia la boca
STRAP_WIDTH_CM = 2.5
# Objetos planos: (ancho, alto, espesor, holgura de ancho, holgura de alto).
COZY_FLAT: dict[CozyItem, tuple[float, float, float, float, float]] = {
    CozyItem.PHONE: (7.5, 15.5, 1.0, 1.0, 1.0),
    CozyItem.GLASSES: (6.5, 15.5, 4.0, 1.0, 1.0),
    CozyItem.PENCIL_CASE: (20.0, 9.0, 3.0, 0.0, 0.0),
    CozyItem.LAPTOP: (30.5, 21.5, 1.6, 2.0, 1.0),
}
LAPTOP_FLAP_SHARE = 0.4
LOOP_CM = 6.0  # presilla para colgar o para el boton
KNIT_POUCH_EDGE_ROWS = 4


# ---------------------------------------------------------------------------
# Contexto: tecnica, punto y densidad.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ctx:
    spec: GarmentSpec
    params: PatternParams  # con la densidad fijada
    gauge: Gauge
    craft: Craft
    kind: StitchKind  # punto de crochet, o KNIT
    stitch_id: str
    tight: bool
    garter: bool
    warnings: list[Warning] = field(default_factory=list)

    @property
    def spc(self) -> float:
        return self.gauge.stitches_per_cm

    @property
    def rpc(self) -> float:
        return self.gauge.rows_per_cm

    def sts(self, cm: float, minimum: int = 1) -> int:
        return max(minimum, round_half_up(cm * self.spc))

    def rows(self, cm: float, minimum: int = 1) -> int:
        return max(minimum, round_half_up(cm * self.rpc))


def _craft(spec: GarmentSpec) -> Craft:
    return "crochet" if spec.tecnica is Technique.CROCHET else "knit"


def context(
    spec: GarmentSpec,
    params: PatternParams,
    *,
    crochet_default: str = "crochet_sc",
    garter: bool = False,
    tight: bool = False,
) -> Ctx:
    """Densidad de la pieza. Sin muestra medida: CYC del grosor (pb/mpa/pa en
    crochet; jersey en agujas). En punto bobo, 2 hileras (un lomo) por cada
    punto de ancho; lo firme (canastos, agarraderas), mas apretado."""
    craft = _craft(spec)
    if craft == "crochet":
        wanted = catalog_id_for_name(spec.punto_base) if spec.punto_base else crochet_default
        stitch_id = wanted if wanted in _CROCHET_KINDS else crochet_default
        base = crochet_gauge(params.peso_hilo.value, stitch_id)
        factor = CROCHET_TIGHTNESS if tight else 1.0
        kind = _CROCHET_KINDS[stitch_id]
    else:
        stitch_id = "garter" if garter else "stockinette"
        base = DEFAULT_GAUGES.get(params.peso_hilo.value, DEFAULT_GAUGES["dk"])
        if garter:
            base = Gauge(stitches_per_10cm=base.stitches_per_10cm, rows_per_10cm=2 * base.stitches_per_10cm)
        factor = KNIT_TIGHTNESS if tight else 1.0
        kind = StitchKind.KNIT
    if params.densidad is None:
        gauge = Gauge(
            stitches_per_10cm=round(base.stitches_per_10cm * factor, 1),
            rows_per_10cm=round(base.rows_per_10cm * factor, 1),
        )
        params = params.model_copy(update={"densidad": gauge})
    assert params.densidad is not None
    return Ctx(spec, params, params.densidad, craft, kind, stitch_id, tight, garter and craft == "knit")


def _dim(params: PatternParams, *keys: str, default: float) -> float:
    for key in keys:
        if key in params.dimensiones_cm:
            return params.dimensiones_cm[key]
        if key in params.medidas_cm:
            return params.medidas_cm[key]
    return default


def _shape_dims(params: PatternParams, shape: FlatShape, default: Dims) -> Dims:
    if shape is FlatShape.CIRCLE:
        d = _dim(params, "diameter", "width", default=default[0])
        return d, d
    if shape is FlatShape.SQUARE:
        side = _dim(params, "width", "length", default=default[0])
        return side, side
    return _dim(params, "width", default=default[0]), _dim(params, "length", default=default[1])


# ---------------------------------------------------------------------------
# Piezas (secciones de la IR).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Shaped:
    section: Section
    width_cm: float  # real, despues de redondear
    length_cm: float
    layout: tuple[int, int] = (0, 0)  # ovalo: (pts del extremo al empezar, pts por extremo)


def _target(key: str, cm: float, rows_per_cm: float, units: float = 1.0) -> SectionTarget:
    """Objetivo de largo con la tolerancia del redondeo (media vuelta por
    cada `units` vueltas que suman al largo, mas un margen minimo)."""
    return SectionTarget(
        measurement_key=key,
        target_cm=cm,
        tolerance_cm=max(0.5, units * 0.5 / rows_per_cm + 0.01),
        dimension="length",
    )


def _section(
    section_id: str,
    name_key: str,
    mode: Literal["flat", "round"],
    steps: Sequence[Step],
    *,
    start: int = 0,
    target: SectionTarget | None = None,
    row_count: int | None = None,
    copies: int = 1,
    bind_off: bool = True,
    note_keys: tuple[str, ...] = (),
    end_note_keys: tuple[str, ...] = (),
    meta: dict[str, int] | None = None,
) -> Section:
    info = {"row_count": row_count if row_count is not None else len(steps), "copies": copies}
    if meta:
        info.update(meta)
    return Section(
        id=section_id,
        name_key=name_key,
        mode=mode,
        steps=tuple(steps),
        start_stitches=start,
        end_stitches=steps[-1].stitch_count_end,
        target=target,
        meta=info,
        bind_off=bind_off,
        note_keys=note_keys,
        end_note_keys=end_note_keys,
    )


def circle_piece(
    ctx: Ctx, diameter: float, section_id: str, name_key: str, *, copies: int = 1, bind_off: bool = True
) -> Shaped:
    if ctx.craft == "crochet":
        inc = circle_increase(ctx.spc, ctx.rpc)
        rounds = ctx.rows(diameter / 2, minimum=2)
        steps = crochet_circle(ctx.kind, inc, rounds)
        notes: tuple[str, ...] = ("home.note.joined_rounds",)
    else:
        final = max(2, round_half_up(pi * diameter * ctx.spc / KNIT_SECTORS)) * KNIT_SECTORS
        edge = 2 if bind_off else 0
        rounds = max(ctx.rows(diameter / 2, minimum=2), final // KNIT_SECTORS + edge)
        steps = knit_circle(final, rounds, edge=edge)
        notes = ()
    actual = 2 * rounds / ctx.rpc
    section = _section(
        section_id,
        name_key,
        "round",
        steps,
        target=_target("diameter", diameter, ctx.rpc, 2),
        row_count=2 * rounds,
        copies=copies,
        bind_off=bind_off,
        note_keys=notes,
    )
    return Shaped(section, actual, actual)


def oval_piece(
    ctx: Ctx, width: float, length: float, section_id: str, name_key: str, *, copies: int = 1, bind_off: bool = True
) -> Shaped:
    """Ovalo de crochet; la cadena va a lo largo de la medida mayor."""
    long, short = max(width, length), min(width, length)
    rounds = ctx.rows(short / 2, minimum=2)
    straight = ctx.sts(long - short)
    end_incs = max(3, round_half_up(circle_increase(ctx.spc, ctx.rpc) / 2))
    steps, head, end = crochet_oval(ctx.kind, straight, end_incs, rounds)
    short_actual = 2 * rounds / ctx.rpc
    section = _section(
        section_id,
        name_key,
        "round",
        steps,
        target=_target("width", short, ctx.rpc, 2),
        row_count=2 * rounds,
        copies=copies,
        bind_off=bind_off,
        note_keys=("home.note.joined_rounds",),
        meta={"straight": straight, "explicit_rounds": 1},
    )
    return Shaped(section, straight / ctx.spc + short_actual, short_actual, (head, end))


def rows_piece(
    ctx: Ctx,
    width: float,
    length: float,
    section_id: str,
    name_key: str,
    *,
    copies: int = 1,
    bind_off: bool = True,
    stitch_id: str | None = None,
    band: tuple[str, float] | None = None,
    multiple: int = 1,
) -> Shaped:
    """Rectangulo en hileras: cadena base (crochet) o montaje (agujas).
    `band`: (punto, cm) de una franja al principio (borde del sobre)."""
    pattern = get_stitch(stitch_id or ctx.stitch_id)
    multiple = lcm(multiple, pattern.multiple, get_stitch(band[0]).multiple if band else 1)
    stitches = adjust_stitches(ctx.sts(width, minimum=2), multiple, mode="nearest")
    rows = ctx.rows(length, minimum=2)
    if ctx.garter:
        rows = max(2, 2 * round_half_up(length * ctx.rpc / 2))  # lomos completos
    start_kind = StitchKind.CH if ctx.craft == "crochet" else StitchKind.CAST_ON
    first_note = "home.note.crochet_chain" if ctx.craft == "crochet" else "pattern.note.cast_on_panel"
    steps = [build_step(1, 0, (Op(start_kind, times=stitches),), note_key=first_note)]
    band_rows = 0
    if band is not None:
        band_rows = ctx.rows(band[1], minimum=2)
        band_rows += band_rows % 2
        band_pattern = get_stitch(band[0])
        for row in range(1, band_rows + 1):
            note = "home.note.band" if row == 1 else None
            steps.append(build_step(row + 1, stitches, expand_row(band_pattern, stitches, row), note_key=note))
    for row in range(1, rows - band_rows + 1):
        note = None
        if row == 1 and ctx.garter:
            note = "home.note.garter_rows"
        elif row == 1 and ctx.craft == "crochet":
            note = "home.note.crochet_rows"
        elif row == 1 and pattern.id == "stockinette":
            note = "pattern.note.flat_panel"
        steps.append(
            build_step(len(steps) + 1, stitches, expand_row(pattern, stitches, row), note_key=note)
        )
    section = _section(
        section_id,
        name_key,
        "flat",
        steps,
        target=_target(f"{section_id}_length", length, ctx.rpc, 2 if ctx.garter else 1),
        row_count=rows,
        copies=copies,
        bind_off=bind_off,
        meta={"band_rows": band_rows, "garter_gauge": int(ctx.garter)},
    )
    return Shaped(section, stitches / ctx.spc, rows / ctx.rpc)


def shape_piece(
    ctx: Ctx,
    shape: FlatShape,
    dims: Dims,
    section_id: str,
    name_key: str,
    *,
    copies: int = 1,
    bind_off: bool = True,
) -> Shaped:
    width, length = dims
    if shape is FlatShape.CIRCLE:
        return circle_piece(ctx, width, section_id, name_key, copies=copies, bind_off=bind_off)
    if shape is FlatShape.OVAL:
        return oval_piece(ctx, width, length, section_id, name_key, copies=copies, bind_off=bind_off)
    return rows_piece(ctx, width, length, section_id, name_key, copies=copies, bind_off=bind_off)


def _shape_measurements(shape: FlatShape, piece: Shaped, dims: Dims, ctx: Ctx) -> list[Measurement]:
    row_tol = 0.5 / ctx.rpc + 0.01
    if shape is FlatShape.CIRCLE:
        return [
            Measurement("diameter", piece.width_cm, dims[0], max(1.0, 2 * row_tol), "width"),
            Measurement("circumference", piece.section.end_stitches / ctx.spc, None, 0.0, "circumference"),
        ]
    if shape is FlatShape.OVAL:
        long, short = max(dims), min(dims)
        return [
            Measurement("length", piece.width_cm, long, max(1.0, 2 * row_tol + 0.5 / ctx.spc), "length"),
            Measurement("width", piece.length_cm, short, max(1.0, 2 * row_tol), "width"),
        ]
    return [
        Measurement("width", piece.width_cm, dims[0], max(1.5, 1.0 / ctx.spc), "width"),
        Measurement("length", piece.length_cm, dims[1], max(1.0, 2 * row_tol), "length"),
    ]


# ---------------------------------------------------------------------------
# Patron.
# ---------------------------------------------------------------------------


def _area(sections: Sequence[Section], gauge: Gauge) -> float:
    total = 0.0
    for section in sections:
        counts = sum(step.stitch_count_end for step in section.steps)
        total += counts * section.meta.get("copies", 1)
    return total / gauge.stitches_per_cm / gauge.rows_per_cm


def _pattern(
    ctx: Ctx,
    family: str,
    title_key: str,
    sections: Sequence[Section],
    measurements: Sequence[Measurement],
    *,
    notions: tuple[str, ...] = (),
    finishing: Sequence[Note] = (),
    joins: Sequence[JoinCheck] = (),
    warnings: Sequence[Warning] = (),
) -> Pattern:
    params = ctx.params
    meters, grams = estimate_yarn(_area(sections, ctx.gauge), params.peso_hilo)
    if ctx.craft == "crochet":
        hook: float | None = params.ganchillo_mm or (
            TOY_HOOK_MM[params.peso_hilo] if ctx.tight else default_hook_mm(params.peso_hilo)
        )
        needle: float | None = None
        tools: tuple[str, ...] = ("notion.crochet_hook", "notion.stitch_markers")
    else:
        hook = None
        needle = params.aguja_mm or (
            TOY_NEEDLE_MM[params.peso_hilo] if ctx.tight else default_needle_mm(params.peso_hilo)
        )
        tools = ()
    materials = Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=needle,
        hook_mm=hook,
        meters=meters,
        grams=grams,
        notions=(*tools, *notions, "notion.tapestry_needle"),
        colors=tuple(ctx.spec.colorwork.paleta) if ctx.spec.colorwork else (),
    )
    gauge_warning = (
        Warning("crochet_gauge", "warning.crochet_gauge", severity="info")
        if ctx.craft == "crochet"
        else Warning("gauge_sample", "warning.gauge_sample", severity="info")
    )
    all_warnings = [
        gauge_warning,
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("home_sizes", "warning.home.sizes", severity="info"),
        *ctx.warnings,
        *warnings,
    ]
    if ctx.tight:
        all_warnings.append(Warning("home_firm", f"warning.home.firm.{ctx.craft}", severity="info"))
    digest = hashlib.sha256(
        (ctx.spec.model_dump_json() + params.model_dump_json() + family).encode("utf-8")
    ).hexdigest()[:12]
    meta = PatternMeta(
        id=digest,
        family=family,
        title_key=title_key,
        size=params.talla,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )
    return Pattern(
        meta=meta,
        spec=ctx.spec,
        params=params,
        sections=tuple(sections),
        measurements=tuple(measurements),
        materials=materials,
        warnings=tuple(all_warnings),
        joins=tuple(joins),
        finishing=tuple(finishing),
    )


def _knit_oval(ctx_warnings: list[Warning], craft: Craft, shape: FlatShape) -> FlatShape:
    """Agujas no ofrece ovalo (no hay una construccion simple y comun):
    rectangulo, con aviso."""
    if craft == "knit" and shape is FlatShape.OVAL:
        ctx_warnings.append(Warning("home_knit_oval", "warning.home.knit_oval"))
        return FlatShape.RECTANGLE
    return shape


def _loop_note(ctx: Ctx, key: str) -> Note:
    return Note(f"{key}.{ctx.craft}", {"n": ctx.sts(LOOP_CM, minimum=6)})


# ---------------------------------------------------------------------------
# Piezas planas.
# ---------------------------------------------------------------------------


def generate_flat_item(spec: GarmentSpec, params: PatternParams) -> Pattern:
    item = spec.objeto_plano or FlatItem.DISHCLOTH
    default_shape, sizes = FLAT_ITEMS[item]
    warnings: list[Warning] = []
    shape = _knit_oval(warnings, _craft(spec), spec.forma_plana or default_shape)
    dims = _shape_dims(params, shape, sizes[shape])
    if (
        _craft(spec) == "crochet"
        and spec.motivo is not None
        and shape in {FlatShape.CIRCLE, FlatShape.SQUARE}
        and item in {FlatItem.DOILY, FlatItem.COASTER, FlatItem.PLACEMAT}
    ):
        # Carpetita o posavasos con un motivo visible: motor de motivos.
        from engine.garments.motif import generate_crochet_motif

        motif = spec.motivo.model_copy(update={"forma": MotifShape(shape.value)})
        size = {"size": dims[0], **params.dimensiones_cm}
        return generate_crochet_motif(
            spec.model_copy(update={"motivo": motif}), params.model_copy(update={"dimensiones_cm": size})
        )
    potholder = item is FlatItem.POTHOLDER
    ctx = context(
        spec,
        params,
        crochet_default=FLAT_CROCHET_STITCH[item],
        garter=shape in {FlatShape.SQUARE, FlatShape.RECTANGLE},
        tight=potholder,
    )
    copies = 2 if potholder else 1
    name = "section.home_potholder_sides" if potholder else "section.home_piece"
    piece = shape_piece(ctx, shape, dims, "piece", name, copies=copies)
    finishing: list[Note] = []
    if potholder:
        finishing.append(Note(f"finishing.home.potholder_join.{ctx.craft}", {}))
        finishing.append(_loop_note(ctx, "finishing.home.hanging_loop"))
    elif item is FlatItem.DOILY and ctx.craft == "crochet":
        finishing.append(Note("finishing.home.doily_starch", {}))
    if ctx.garter:
        warnings.append(Warning("home_garter", "warning.home.garter", severity="info"))
    return _pattern(
        ctx,
        "home_flat",
        f"title.home_{item.value}",
        [piece.section],
        _shape_measurements(shape, piece, dims, ctx),
        finishing=finishing,
        warnings=warnings,
    )


def generate_rug(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = _craft(spec)
    warnings: list[Warning] = []
    default = FlatShape.CIRCLE if craft == "crochet" else FlatShape.RECTANGLE
    shape = _knit_oval(warnings, craft, spec.forma_plana or default)
    dims = _shape_dims(params, shape, RUG_SIZES[shape])
    ctx = context(spec, params, garter=shape in {FlatShape.SQUARE, FlatShape.RECTANGLE})
    piece = shape_piece(ctx, shape, dims, "rug", "section.home_rug")
    warnings.append(Warning("home_rug", "warning.home.rug", severity="info"))
    if ctx.garter:
        warnings.append(Warning("home_garter", "warning.home.garter", severity="info"))
    return _pattern(
        ctx,
        "home_rug",
        "title.home_rug",
        [piece.section],
        _shape_measurements(shape, piece, dims, ctx),
        notions=("notion.home.non_slip",),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Almohadon.
# ---------------------------------------------------------------------------

_PILLOW_KNIT_STITCHES = {"stockinette", "seed", "moss"}


def generate_pillow(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = _craft(spec)
    warnings: list[Warning] = []
    shape = _knit_oval(warnings, craft, spec.forma_plana or FlatShape.SQUARE)
    insert = _shape_dims(params, shape, PILLOW_SIZES[shape])
    dims = (insert[0] - PILLOW_NEGATIVE_EASE_CM, insert[1] - PILLOW_NEGATIVE_EASE_CM)
    ctx = context(spec, params)
    measurements: list[Measurement]
    if craft == "crochet" or shape is FlatShape.CIRCLE:
        # Dos caras iguales que se unen alrededor (crochet, o circulos).
        piece = shape_piece(ctx, shape, dims, "panel", "section.home_pillow_panels", copies=2)
        sections = [piece.section]
        measurements = _shape_measurements(shape, piece, dims, ctx)
        finishing = [Note(f"finishing.home.pillow_join.{craft}", {})]
        joins: list[JoinCheck] = []
    else:
        wanted = catalog_id_for_name(spec.punto_base) if spec.punto_base else "stockinette"
        stitch = wanted if wanted in _PILLOW_KNIT_STITCHES else "stockinette"
        if spec.punto_base is not None and stitch != wanted:
            warnings.append(Warning("home_stitch", "warning.home.stitch", severity="info"))
        multiple = lcm(get_stitch(stitch).multiple, get_stitch("rib_1x1").multiple)
        front = rows_piece(
            ctx, dims[0], dims[1], "front", "section.home_pillow_front", stitch_id=stitch, multiple=multiple
        )
        back = rows_piece(
            ctx,
            dims[0],
            PILLOW_BACK_SHARE * dims[1],
            "back",
            "section.home_pillow_backs",
            copies=2,
            stitch_id=stitch,
            band=("rib_1x1", PILLOW_BAND_CM),
            multiple=multiple,
        )
        sections = [front.section, back.section]
        measurements = [
            Measurement("width", front.width_cm, dims[0], max(1.5, 1.0 / ctx.spc), "width"),
            Measurement("length", front.length_cm, dims[1], max(1.0, 1.0 / ctx.rpc + 0.01), "length"),
        ]
        finishing = [Note("finishing.home.pillow_envelope", {"n": back.section.meta["band_rows"]})]
        joins = [JoinCheck("join.home_pillow", (CountRef("front", "end"),), (CountRef("back", "end"),))]
    warnings.append(
        Warning(
            "home_pillow_insert",
            "warning.home.pillow_insert",
            severity="info",
            params={"w": f"{insert[0]:g}", "l": f"{insert[1]:g}"},
        )
    )
    return _pattern(
        ctx,
        "home_pillow",
        "title.home_pillow",
        sections,
        measurements,
        notions=("notion.home.pillow_insert",),
        finishing=finishing,
        joins=joins,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Paredes (canasto y funda redonda).
# ---------------------------------------------------------------------------


def _base_and_pickup(
    ctx: Ctx, shape: FlatShape, dims: Dims
) -> tuple[Shaped, list[Item] | None, int, float]:
    """Base y, para la base rectangular, la vuelta que levanta los puntos
    alrededor. Devuelve (base, vuelta de levantar o None, pts de la pared,
    centro de la primera asa en pts desde el comienzo de la vuelta)."""
    if shape in {FlatShape.SQUARE, FlatShape.RECTANGLE}:
        width, depth = max(dims), min(dims)
        base = rows_piece(ctx, width, depth, "base", "section.home_base", bind_off=False, stitch_id=(
            ctx.stitch_id if ctx.craft == "crochet" else "stockinette"
        ))
        long = base.section.end_stitches
        side = ctx.sts(depth, minimum=2)
        edge = StitchKind.CROCHET_EDGE if ctx.craft == "crochet" else StitchKind.PICK_UP
        pickup: list[Item] = [Op(ctx.kind, times=long), Op(edge, times=side), Op(edge, times=long), Op(edge, times=side)]
        count = 2 * (long + side)
        # Asas centradas en los lados cortos si entran; si no, en los largos.
        center = long + side / 2 if side > ctx.sts(HANDLE_WIDTH_CM) + 4 else long / 2
        return base, pickup, count, center
    base = (
        circle_piece(ctx, dims[0], "base", "section.home_base", bind_off=False)
        if shape is FlatShape.CIRCLE
        else oval_piece(ctx, dims[0], dims[1], "base", "section.home_base", bind_off=False)
    )
    count = base.section.end_stitches
    if shape is FlatShape.OVAL:
        head, end = base.layout
        center = head + base.section.meta["straight"] + end / 2
    else:
        center = count / 4
    return base, None, count, center


def _walls(
    ctx: Ctx,
    first_number: int,
    count: int,
    height: float,
    *,
    pickup: list[Item] | None = None,
    handles_center: float | None = None,
    top_count: int | None = None,
    sectors: int = 6,
    stitch_id: str | None = None,
) -> tuple[list[Step], int]:
    """Paredes rectas desde el borde de la base: (vueltas, vueltas de alto).

    Crochet: vuelta por la hebra de atras (marca el borde) y vueltas lisas.
    Agujas: una vuelta reves (doblez), jersey o elastico, y 4 vueltas de
    borde en elastico 1x1, que no se enrolla. Asas: dos aberturas opuestas a 2,5 cm del borde.
    `top_count`: se cierra hacia la boca (mate) en el tercio de arriba.
    """
    total = ctx.rows(height, minimum=4)
    knit = ctx.craft == "knit"
    steps: list[Step] = []
    number = first_number
    if pickup is not None:
        note = "home.note.walls_pickup_crochet" if not knit else "home.note.walls_pickup_knit"
        start = sum(item.consumes for item in pickup)
        steps.append(build_step(number, start, pickup, note_key=note))
        number += 1
    first_note = "home.note.walls_purl" if knit else "home.note.walls_blo"
    first_kind = StitchKind.PURL if knit else ctx.kind
    steps.append(build_step(number, count, (Op(first_kind, times=count),), note_key=first_note))
    number += 1
    edge = 4 if knit else 0
    shaping: list[int] = []
    if top_count is not None and top_count < count:
        zone = max((count - top_count) // sectors, round_half_up(MATE_SHAPING_SHARE * total))
        shaping = spread(count, top_count, zone, sectors)
    handle_at = -1
    handle_w = 0
    if handles_center is not None:
        handle_w = ctx.sts(HANDLE_WIDTH_CM)
        handle_w = min(handle_w, count // 2 - 4)
        handle_at = total - edge - ctx.rows(HANDLE_FROM_TOP_CM, minimum=2) - 1
    pattern = get_stitch(stitch_id) if stitch_id else None
    plain = total - len(steps) - len(shaping) - edge
    if plain < 0:
        raise ImpossibleProportionsError("error.too_small_for_yarn", weight=ctx.params.peso_hilo.value, target=round(height, 1))
    row = 0
    while row < plain:
        if len(steps) == handle_at and handle_w >= 2 and row + 2 <= plain:
            opened, closed = handle_round(
                number, count, handle_w, round_half_up(handles_center or 0), ctx.kind, craft=ctx.craft
            )
            steps += [opened, closed]
            number += 2
            row += 2
            continue
        items = expand_row(pattern, count, row + 1, in_the_round=True) if pattern else (Op(ctx.kind, times=count),)
        steps.append(build_step(number, count, items))
        number += 1
        row += 1
    dec = StitchKind.K2TOG if knit else StitchKind.CROCHET_DEC
    noted = False
    for target in shaping:
        changes = count - target
        items_list = change_items(count, changes, ctx.kind, dec)
        dec_note = "home.note.top_decrease" if changes and not noted else None
        noted = noted or bool(changes)
        steps.append(build_step(number, count, items_list, note_key=dec_note))
        count = target
        number += 1
    for index in range(edge):
        items = expand_row(get_stitch("rib_1x1"), count, index + 1, in_the_round=True)
        edge_note = "home.note.rib_edge" if index == 0 else None
        steps.append(build_step(number, count, items, note_key=edge_note))
        number += 1
    return steps, len(steps)


# ---------------------------------------------------------------------------
# Canasto.
# ---------------------------------------------------------------------------


def generate_basket(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = _craft(spec)
    warnings: list[Warning] = []
    shape = _knit_oval(warnings, craft, spec.forma_plana or FlatShape.CIRCLE)
    dims = _shape_dims(params, shape, BASKET_SIZES[shape])
    height = _dim(params, "height", default=BASKET_HEIGHT_CM)
    ctx = context(spec, params, crochet_default="crochet_sc", tight=True)
    base, pickup, count, center = _base_and_pickup(ctx, shape, dims)
    first = len(base.section.steps) + 1
    steps, rounds = _walls(
        ctx,
        first,
        count,
        height,
        pickup=pickup,
        handles_center=center if height >= HANDLE_MIN_HEIGHT_CM else None,
    )
    handles = any(step.note_key == "home.note.handles_open" for step in steps)
    start = base.section.end_stitches
    walls = _section(
        "walls",
        "section.home_walls",
        "round",
        steps,
        start=start,
        target=_target("height", height, ctx.rpc),
        row_count=rounds,
        meta={"continue": 1},
        note_keys=("home.note.walls_continue",),
    )
    measurements = _base_measurements(shape, base, dims, ctx)
    measurements.append(Measurement("height", rounds / ctx.rpc, height, max(1.0, 0.5 / ctx.rpc + 0.01), "length"))
    if handles:
        warnings.append(Warning("home_handles", "warning.home.handles", severity="info"))
    return _pattern(
        ctx, "home_basket", "title.home_basket", [base.section, walls], measurements, warnings=warnings
    )


def _base_measurements(shape: FlatShape, base: Shaped, dims: Dims, ctx: Ctx) -> list[Measurement]:
    if shape is FlatShape.CIRCLE:
        return [Measurement("diameter", base.width_cm, dims[0], max(1.0, 1.0 / ctx.rpc + 0.01), "width")]
    long, short = max(dims), min(dims)
    if shape is FlatShape.OVAL:
        return [
            Measurement("length", base.width_cm, long, max(1.0, 1.0 / ctx.rpc + 0.5 / ctx.spc + 0.01), "length"),
            Measurement("width", base.length_cm, short, max(1.0, 1.0 / ctx.rpc + 0.01), "width"),
        ]
    return [
        Measurement("length", base.width_cm, long, max(1.5, 1.0 / ctx.spc), "length"),
        Measurement("width", base.length_cm, short, max(1.0, 0.5 / ctx.rpc + 0.01), "width"),
    ]


# ---------------------------------------------------------------------------
# Fundas.
# ---------------------------------------------------------------------------


def generate_cozy(spec: GarmentSpec, params: PatternParams) -> Pattern:
    item = spec.objeto_funda or CozyItem.CUP
    if item in COZY_FLAT:
        return _pouch(spec, params, item)
    return _round_cozy(spec, params, item)


def _round_cozy(spec: GarmentSpec, params: PatternParams, item: CozyItem) -> Pattern:
    craft = _craft(spec)
    default_d, default_h, default_top, default_strap = COZY_ROUND[item]
    diameter = _dim(params, "diameter", "width", default=default_d)
    height = _dim(params, "height", "length", default=default_h)
    top = _dim(params, "top_diameter", default=default_top or diameter) if default_top or "top_diameter" in params.dimensiones_cm else None
    strap = _dim(params, "strap", default=default_strap)
    warnings: list[Warning] = []
    # Paredes en jersey (o en elastico si la foto lo muestra).
    rib = None
    if craft == "knit" and spec.punto_base is not None:
        wanted = catalog_id_for_name(spec.punto_base)
        rib = wanted if wanted in {"rib_1x1", "rib_2x2"} else None
    ctx = context(spec, params, crochet_default="crochet_sc")

    def circumference(d: float) -> float:
        if params.ease_cm is not None:
            return pi * d + params.ease_cm
        return pi * d * (1 + COZY_EASE[craft])

    if craft == "crochet":
        sectors = circle_increase(ctx.spc, ctx.rpc)
        count = max(2, round_half_up(circumference(diameter) * ctx.spc / sectors)) * sectors
        base_steps = crochet_circle(ctx.kind, sectors, count // sectors)
        base_notes: tuple[str, ...] = ("home.note.joined_rounds",)
    else:
        sectors = KNIT_SECTORS
        count = max(2, round_half_up(circumference(diameter) * ctx.spc / sectors)) * sectors
        rounds = max(ctx.rows(count / ctx.spc / pi / 2, minimum=2), count // sectors)
        base_steps = knit_circle(count, rounds)
        base_notes = ()
    top_count = None
    if top is not None and top < diameter and rib is None:
        top_count = max(2, round_half_up(circumference(top) * ctx.spc / sectors)) * sectors
    base_rounds = len(base_steps)
    base = _section(
        "base",
        "section.home_base",
        "round",
        base_steps,
        row_count=2 * base_rounds,
        bind_off=False,
        note_keys=base_notes,
    )
    steps, rounds = _walls(
        ctx, base_rounds + 1, count, height, top_count=top_count, sectors=sectors, stitch_id=rib
    )
    walls = _section(
        "walls",
        "section.home_walls",
        "round",
        steps,
        start=count,
        target=_target("height", height, ctx.rpc),
        row_count=rounds,
        meta={"continue": 1},
        note_keys=("home.note.walls_continue",),
    )
    sections = [base, walls]
    measurements = [
        Measurement(
            "circumference",
            count / ctx.spc,
            circumference(diameter),
            sectors / ctx.spc / 2 + 0.01,
            "circumference",
        ),
        Measurement("height", rounds / ctx.rpc, height, max(1.0, 0.5 / ctx.rpc + 0.01), "length"),
    ]
    if top_count is not None and top is not None:
        measurements.append(
            Measurement(
                "home_top", top_count / ctx.spc, circumference(top), sectors / ctx.spc / 2 + 0.01, "circumference"
            )
        )
    finishing: list[Note] = []
    if strap > 0:
        strap_sts = ctx.sts(strap, minimum=10)
        # Agujas: punto bobo, un lomo (2 hileras) por cada punto de ancho.
        strap_rows = ctx.rows(STRAP_WIDTH_CM, minimum=2) if craft == "crochet" else 2 * ctx.sts(STRAP_WIDTH_CM, minimum=3)
        strap_kind = StitchKind.CH if craft == "crochet" else StitchKind.CAST_ON
        strap_steps = [build_step(1, 0, (Op(strap_kind, times=strap_sts),), note_key="home.note.strap_start")]
        row_kind = ctx.kind
        for row in range(strap_rows):
            strap_steps.append(build_step(row + 2, strap_sts, (Op(row_kind, times=strap_sts),)))
        sections.append(_section("strap", "section.home_strap", "flat", strap_steps, row_count=strap_rows))
        measurements.append(Measurement("home_strap", strap_sts / ctx.spc, strap, 1.0 / ctx.spc + 0.01, "length"))
        finishing.append(Note("finishing.home.strap", {"n": walls.end_stitches // 2}))
    finishing.append(Note(f"finishing.home.cozy_round.{item.value}", {}))
    return _pattern(
        ctx,
        "home_cozy",
        f"title.home_cozy_{item.value}",
        sections,
        measurements,
        finishing=finishing,
        warnings=[*warnings, Warning("home_cozy_fit", f"warning.home.cozy_fit.{craft}", severity="info")],
    )


def _pouch(spec: GarmentSpec, params: PatternParams, item: CozyItem) -> Pattern:
    """Bolsita plana: dos caras y fondo. Crochet: en redondo desde una cadena
    trabajada por los dos lados (sin costuras). Agujas: una tira que se dobla
    al medio y se cose a los costados."""
    craft = _craft(spec)
    w, h, depth, ease_w, ease_h = COZY_FLAT[item]
    width = _dim(params, "width", default=w)
    height = _dim(params, "height", "length", default=h)
    depth = _dim(params, "depth", default=depth)
    flat_w = width + depth + (params.ease_cm / 2 if params.ease_cm is not None else ease_w)
    flat_h = height + ease_h
    flap = LAPTOP_FLAP_SHARE * height if item is CozyItem.LAPTOP else 0.0
    ctx = context(spec, params, crochet_default="crochet_sc")
    sections: list[Section] = []
    finishing: list[Note] = []
    if craft == "crochet":
        chain = ctx.sts(flat_w, minimum=3)
        rounds = ctx.rows(flat_h, minimum=3)
        steps = [build_step(1, 0, (Op(StitchKind.CH, times=chain),), note_key="home.note.crochet_chain")]
        first: list[Item] = [Op(ctx.kind, times=chain), Op(StitchKind.CROCHET_EDGE, times=chain)]
        steps.append(build_step(2, chain, first, note_key="home.note.pouch_first", note_params=(("n", str(chain)),)))
        steps += plain_rounds(3, 2 * chain, rounds - 1, ctx.kind)
        sections.append(
            _section(
                "pouch",
                "section.home_pouch",
                "round",
                steps,
                target=_target("height", flat_h, ctx.rpc),
                row_count=rounds,
                bind_off=not flap,
                note_keys=("home.note.joined_rounds",),
            )
        )
        width_sts = chain
        height_cm = rounds / ctx.rpc
        if flap:
            flap_rows = ctx.rows(flap, minimum=2)
            pattern = get_stitch(ctx.stitch_id)
            flap_steps = [
                build_step(
                    row,
                    chain,
                    expand_row(pattern, chain, row),
                    note_key="home.note.flap_start" if row == 1 else None,
                    note_params=(("n", str(chain)),) if row == 1 else (),
                )
                for row in range(1, flap_rows + 1)
            ]
            sections.append(
                _section(
                    "flap",
                    "section.home_flap",
                    "flat",
                    flap_steps,
                    start=chain,
                    target=_target("home_flap", flap, ctx.rpc),
                    meta={"continue": 1},
                )
            )
    else:
        stitches = ctx.sts(flat_w, minimum=4)
        side_rows = ctx.rows(flat_h, minimum=4)
        total = 2 * side_rows + (ctx.rows(flap, minimum=2) if flap else 0)
        edge = KNIT_POUCH_EDGE_ROWS
        steps = [build_step(1, 0, (Op(StitchKind.CAST_ON, times=stitches),), note_key="home.note.garter_edge_rows")]
        stock = get_stitch("stockinette")
        for row in range(1, total + 1):
            in_edge = row <= edge or row > total - edge
            note = None
            if row == edge + 1:
                note = "pattern.note.flat_panel"
            items = (Op(StitchKind.KNIT, times=stitches),) if in_edge else expand_row(stock, stitches, row - edge)
            steps.append(build_step(row + 1, stitches, items, note_key=note))
        sections.append(
            _section(
                "pouch",
                "section.home_pouch_knit",
                "flat",
                steps,
                target=_target("length", total / ctx.rpc, ctx.rpc),
                row_count=total,
            )
        )
        finishing.append(Note("finishing.home.pouch_fold", {"n": side_rows, "cm": f"{side_rows / ctx.rpc:.1f}"}))
        width_sts = stitches
        height_cm = side_rows / ctx.rpc
    measurements = [
        Measurement("width", width_sts / ctx.spc, flat_w, max(1.0, 0.5 / ctx.spc + 0.01), "width"),
        Measurement("height", height_cm, flat_h, max(1.0, 0.5 / ctx.rpc + 0.01), "length"),
    ]
    notions: tuple[str, ...] = ()
    if flap:
        measurements.append(Measurement("home_flap", ctx.rows(flap, minimum=2) / ctx.rpc, flap, max(1.0, 0.5 / ctx.rpc + 0.01), "length"))
        finishing.append(_loop_note(ctx, "finishing.home.button_loop"))
        notions = ("notion.home.button",)
    if item is CozyItem.PENCIL_CASE:
        zipper = max(10, round_half_up(width))
        finishing.append(Note("finishing.home.zipper", {"n": zipper}))
        notions = ("notion.home.zipper",)
    finishing.append(Note(f"finishing.home.pouch.{item.value}", {}))
    return _pattern(
        ctx,
        "home_pouch",
        f"title.home_cozy_{item.value}",
        sections,
        measurements,
        notions=notions,
        finishing=finishing,
        warnings=[Warning("home_pouch_fit", "warning.home.pouch_fit", severity="info")],
    )


__all__ = [
    "generate_basket",
    "generate_cozy",
    "generate_flat_item",
    "generate_pillow",
    "generate_rug",
]
