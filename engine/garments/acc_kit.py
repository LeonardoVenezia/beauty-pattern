"""Herramientas comunes de los accesorios con forma (gorros, manos, pies).

Las piezas se describen como listas de vueltas (`Row`) y se convierten en
secciones verificables con `build_section`. Una misma forma sirve para dos
agujas y para crochet: `Craft` dice que punto liso, que aumento, que
disminucion y que montaje usa cada tecnica. Todos los numeros salen de la
densidad y de las tablas de talles de este modulo (fuentes en
docs/fuentes.md; lo que no tiene fuente esta marcado ASUNCION).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import split_even
from engine.gauge import Gauge, crochet_gauge
from engine.ir import (
    Item,
    Materials,
    Measurement,
    Op,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import (
    METERS_PER_100G,
    default_hook_mm,
    default_needle_mm,
    estimate_yarn,
)
from engine.rounding import round_half_up
from engine.spec import (
    Finish,
    GarmentSpec,
    PatternParams,
    StitchPatternName,
    Technique,
    Texture,
    resolve_gauge,
)
from engine.stitches.catalog import catalog_id_for_name, expand_row, get_stitch
from engine.stitches.kinds import StitchKind

# ---------------------------------------------------------------------------
# Tablas de talles.
# ---------------------------------------------------------------------------

# Contorno de cabeza adulto (cm). Dentro de los rangos del Craft Yarn Council,
# Head Circumference Chart (mujer 53-58,5; hombre 56-61; verificado
# 2026-11-17). Es la misma tabla que usaba el gorro.
HEAD_BY_SIZE: dict[str, float] = {
    "XS": 52.0,
    "S": 54.0,
    "M": 56.0,
    "L": 58.0,
    "XL": 59.0,
    "2XL": 60.0,
    "3XL": 61.0,
}
# Bebes (meses). CYC: "baby" 35,5-40,5 y "toddler" 40,5-46 cm.
# ASUNCION: el valor de cada tramo de edad dentro de esos rangos.
BABY_SIZES: tuple[str, ...] = ("0-3", "3-6", "6-12")
BABY_HEAD: dict[str, float] = {"0-3": 36.0, "3-6": 40.5, "6-12": 44.0}
# Pie de bebe (contorno, largo). CYC Foot Size Chart, talle 0-4 (6-18 meses):
# contorno 11 cm, largo 7,75-11,5 cm. ASUNCION: el reparto por edad.
BABY_FOOT: dict[str, tuple[float, float]] = {
    "0-3": (10.0, 9.0),
    "3-6": (10.5, 10.0),
    "6-12": (11.0, 11.5),
}
# Pie adulto (contorno, largo). CYC Foot Size Chart: mujer 17,5/20,5/23 de
# contorno y 20,25-23 / 23,5-25,5 / 26-28 de largo; hombre 20,5/23/25,5 y
# 23,5-25,5 / 26-28 / 28,5-30,5. ASUNCION: como se reparten en XS-3XL.
ADULT_FOOT: dict[str, tuple[float, float]] = {
    "XS": (17.5, 21.5),
    "S": (17.5, 22.5),
    "M": (20.5, 24.0),
    "L": (20.5, 25.5),
    "XL": (23.0, 27.0),
    "2XL": (23.0, 28.0),
    "3XL": (25.5, 29.5),
}
# Mano (contorno de palma, largo total). CYC Hand Size Charts: mujer S/M/L
# 18/19/20,5 y 16/16,5/19; hombre S/M/L 20,5/21,5/23,5 y 19/20/21,5.
HAND_BY_SIZE: dict[str, tuple[float, float]] = {
    "XS": (18.0, 16.0),
    "S": (18.0, 16.5),
    "M": (19.0, 16.5),
    "L": (20.5, 19.0),
    "XL": (21.5, 20.0),
    "2XL": (23.5, 21.5),
    "3XL": (23.5, 21.5),
}
# ASUNCION (no hay tabla publicada verificada): contorno de pantorrilla y de
# tobillo por talle, valores medios de patrones de polainas publicados.
LEG_BY_SIZE: dict[str, tuple[float, float]] = {
    "XS": (31.0, 20.0),
    "S": (33.0, 21.0),
    "M": (35.0, 22.0),
    "L": (37.0, 23.0),
    "XL": (39.0, 24.0),
    "2XL": (41.0, 25.0),
    "3XL": (43.0, 26.0),
}


def dimension(params: PatternParams, key: str, default: float) -> float:
    if key in params.dimensiones_cm:
        return params.dimensiones_cm[key]
    if key in params.medidas_cm:
        return params.medidas_cm[key]
    return default


def is_baby(params: PatternParams) -> bool:
    return params.talla in BABY_SIZES


def head_cm(params: PatternParams) -> float:
    size = params.talla
    default = BABY_HEAD.get(size) or HEAD_BY_SIZE.get(size.upper(), 56.0)
    return dimension(params, "head", default)


def scale(params: PatternParams, adult_cm: float) -> float:
    """Medida secundaria (alto de borde, largo de orejera...) proporcional a
    la cabeza: la referencia `adult_cm` es para 56 cm de contorno."""
    return adult_cm * head_cm(params) / 56.0


# ---------------------------------------------------------------------------
# Tecnica.
# ---------------------------------------------------------------------------

_CROCHET_KIND = {
    "crochet_sc": StitchKind.SC,
    "crochet_hdc": StitchKind.HDC,
    "crochet_dc": StitchKind.DC,
}


@dataclass(frozen=True)
class Craft:
    """Lo que cambia entre dos agujas y crochet en una pieza con forma."""

    crochet: bool
    plain: StitchKind
    stitch_id: str  # punto base (catalogo) de las partes lisas

    @property
    def dec(self) -> StitchKind:
        return StitchKind.CROCHET_DEC if self.crochet else StitchKind.K2TOG

    @property
    def dec_left(self) -> StitchKind:
        """Disminucion del final de vuelta (en espejo de `dec`)."""
        return StitchKind.CROCHET_DEC if self.crochet else StitchKind.SSK

    @property
    def start(self) -> StitchKind:
        return StitchKind.CH if self.crochet else StitchKind.CAST_ON

    @property
    def multiple(self) -> int:
        return 1 if self.crochet else get_stitch(self.stitch_id).multiple


def knit_base_id(spec: GarmentSpec, default: str = "stockinette") -> str:
    if spec.punto_base is None:
        return default
    pattern_id = catalog_id_for_name(spec.punto_base)
    if pattern_id.startswith("crochet") or pattern_id == "magic_ring":
        return default
    return pattern_id


def crochet_base_id(spec: GarmentSpec, default: str = "crochet_sc") -> str:
    if spec.punto_base is None:
        return default
    pattern_id = catalog_id_for_name(spec.punto_base)
    return pattern_id if pattern_id in _CROCHET_KIND else default


def craft_for(
    spec: GarmentSpec, *, knit_default: str = "stockinette", crochet_default: str = "crochet_sc"
) -> Craft:
    if spec.tecnica is Technique.CROCHET:
        stitch_id = crochet_base_id(spec, crochet_default)
        return Craft(True, _CROCHET_KIND[stitch_id], stitch_id)
    return Craft(False, StitchKind.KNIT, knit_base_id(spec, knit_default))


def with_gauge(craft: Craft, params: PatternParams) -> PatternParams:
    """Crochet sin muestra medida: densidad de referencia del punto base."""
    if not craft.crochet or params.densidad is not None:
        return params
    gauge = crochet_gauge(params.peso_hilo.value, craft.stitch_id)
    return params.model_copy(update={"densidad": gauge})


def is_mesh(spec: GarmentSpec) -> bool:
    """Red (casquete de red, gorro de verano): pa separados por cadenas."""
    return spec.punto_base is StitchPatternName.FILET or any(
        obs.textura is Texture.MESH for obs in spec.texturas
    )


def flat_rate(gauge: Gauge) -> float:
    """Puntos que hay que sumar por vuelta para que un circulo quede plano:
    2 pi x alto de vuelta x pts/cm (la misma regla del gorro y los motivos de
    crochet; en dos agujas da los clasicos 8 aumentos cada 2 vueltas)."""
    return 2 * math.pi * gauge.stitches_per_cm / gauge.rows_per_cm


def nearest_multiple(value: float, multiple: int, *, minimum: int = 1) -> int:
    """Multiplo de `multiple` mas cercano a un valor sin redondear (redondear
    antes y ajustar despues puede alejarse medio motivo de mas)."""
    count = round_half_up(value / multiple) * multiple
    return max(count, multiple * max(1, math.ceil(minimum / multiple)))


def ensure_fits(value_cm: float, target_cm: float, tolerance_cm: float) -> None:
    """Un hilo muy grueso para una pieza chica (escarpin en hilo XXL): el
    minimo de puntos ya se pasa de la medida. Se rechaza con honestidad en
    vez de entregar algo que no cierra."""
    if abs(value_cm - target_cm) > tolerance_cm:
        from engine.garments.base import ImpossibleProportionsError

        raise ImpossibleProportionsError(
            "acc.error.yarn_too_thick", cm=f"{target_cm:.0f}", got=f"{value_cm:.0f}"
        )


def fitted(measurements: Sequence[Measurement]) -> tuple[Measurement, ...]:
    """Medidas de ancho/contorno: si la minima cantidad de puntos ya no entra
    (hilo demasiado grueso para el talle), rechazo honesto."""
    for item in measurements:
        if item.kind != "length" and item.target_cm is not None:
            ensure_fits(item.value_cm, item.target_cm, item.tolerance_cm)
    return tuple(measurements)


def repeat_tolerance(gauge: Gauge, multiple: int, base: float) -> float:
    """Tolerancia de un ancho: la pedida o medio motivo del punto, si el
    motivo es mas ancho (no se puede tejer medio motivo)."""
    return max(base, gauge.cm_for_stitches(multiple) / 2 + 0.05)


# ---------------------------------------------------------------------------
# Vueltas.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    items: tuple[Item, ...]
    note: str | None = None
    params: tuple[tuple[str, str], ...] = ()


def plain(craft: Craft, n: int) -> tuple[Item, ...]:
    return (Op(craft.plain, times=n),)


def shape_items(craft: Craft, n: int, delta: int) -> tuple[Item, ...]:
    """Una vuelta de `n` pts que cambia el conteo en `delta`, con los
    aumentos o disminuciones repartidos parejo."""
    if delta == 0:
        return plain(craft, n)
    unit: Op
    if delta > 0:
        count = delta
        if craft.crochet:
            rest, unit = n - count, Op(StitchKind.CROCHET_INC)
        else:
            rest, unit = n, Op(StitchKind.M1L)
        if count > n:
            raise ValueError(f"no entran {count} aumentos en {n} pts")
    else:
        count = -delta
        rest, unit = n - 2 * count, Op(craft.dec)
        if rest < 0:
            raise ValueError(f"no entran {count} disminuciones en {n} pts")
    groups = split_even(rest, count)
    if len(set(groups)) == 1:
        if groups[0] == 0:
            return (Op(unit.kind, times=count),)
        unit_ops = (Op(craft.plain, times=groups[0]), unit)
        return (Repeat(count, unit_ops),) if count > 1 else unit_ops
    items: list[Item] = []
    for group in groups:
        if group:
            items.append(Op(craft.plain, times=group))
        items.append(unit)
    return tuple(items)


def pattern_rows(
    craft: Craft,
    n: int,
    count: int,
    *,
    round_mode: bool,
    first: int = 1,
    stitch_id: str | None = None,
    note: str | None = None,
    params: tuple[tuple[str, str], ...] = (),
) -> list[Row]:
    """`count` vueltas sin forma en el punto base (o `stitch_id`)."""
    rows: list[Row] = []
    pid = stitch_id or craft.stitch_id
    for index in range(count):
        if pid in _CROCHET_KIND:
            items: tuple[Item, ...] = (Op(_CROCHET_KIND[pid], times=n),)
        else:
            items = expand_row(get_stitch(pid), n, first + index, in_the_round=round_mode)
        rows.append(Row(items, note if index == 0 else None, params if index == 0 else ()))
    return rows


def mesh_items(n: int) -> tuple[Item, ...]:
    """Vuelta de red: (1 pa, 1 cad, saltar 1); conserva el conteo."""
    unit = (Op(StitchKind.DC), Op(StitchKind.CH), Op(StitchKind.SKIP))
    items: list[Item] = [Repeat(n // 2, unit)] if n >= 2 else []
    if n % 2:
        items.append(Op(StitchKind.DC))
    return tuple(items)


def cast_on_row(craft: Craft, n: int, *, round_mode: bool) -> Row:
    note = None
    if craft.crochet:
        note = "acc.note.chain_join" if round_mode else None
    elif round_mode:
        note = "pattern.note.cast_on_join"
    return Row((Op(craft.start, times=n),), note)


def build_section(
    section_id: str,
    name_key: str,
    mode: str,
    start: int,
    rows: Sequence[Row],
    gauge: Gauge,
    *,
    bind_off: bool = False,
    gather: bool = False,
    note_keys: tuple[str, ...] = (),
    end_note_keys: tuple[str, ...] = (),
    meta: dict[str, int] | None = None,
    target: bool = True,
) -> Section:
    """Seccion verificada vuelta por vuelta (build_step falla si una vuelta
    no consume exactamente los puntos que hay)."""
    steps: list[Step] = []
    current = start
    for number, row in enumerate(rows, start=1):
        step = build_step(number, current, row.items, note_key=row.note, note_params=row.params)
        steps.append(step)
        current = step.stitch_count_end
    worked = len(rows) - (1 if start == 0 and rows else 0)
    section_meta: dict[str, int] = {"row_count": worked}
    if gather:
        section_meta["gather"] = 1
    section_meta.update(meta or {})
    return Section(
        id=section_id,
        name_key=name_key,
        mode="round" if mode == "round" else "flat",
        steps=tuple(steps),
        start_stitches=start,
        end_stitches=current,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=gauge.cm_for_rows(worked),
            tolerance_cm=0.5,
            dimension="length",
        )
        if target and worked
        else None,
        meta=section_meta,
        bind_off=bind_off,
        note_keys=note_keys,
        end_note_keys=end_note_keys,
    )


def tie_section(
    craft: Craft, gauge: Gauge, length_cm: float, *, section_id: str = "ties"
) -> Section:
    """Lazo: i-cord de 3 pts (dos agujas) o cadena con pe de vuelta (crochet)."""
    if craft.crochet:
        chains = max(10, gauge.stitches_for_cm(length_cm))
        rows = [
            Row((Op(StitchKind.CH, times=chains),)),
            Row((Op(StitchKind.SLST, times=chains),), "acc.note.tie_crochet"),
        ]
        return build_section(
            section_id,
            "acc.section.ties",
            "flat",
            0,
            rows,
            gauge,
            bind_off=True,
            target=False,
            note_keys=("acc.note.make_two",),
        )
    rows = [Row((Op(StitchKind.CAST_ON, times=3),))]
    count = max(4, gauge.rows_for_cm(length_cm))
    rows += [
        Row((Op(StitchKind.KNIT, times=3),), "acc.note.icord" if i == 0 else None)
        for i in range(count)
    ]
    return build_section(
        section_id,
        "acc.section.ties",
        "round",
        0,
        rows,
        gauge,
        bind_off=True,
        note_keys=("acc.note.make_two",),
    )


# ---------------------------------------------------------------------------
# Pompon.
# ---------------------------------------------------------------------------

POMPOM_FILL = 0.3  # ASUNCION: fraccion del volumen del pompon que ocupa el hilo


@dataclass(frozen=True)
class Pompom:
    diameter_cm: float
    wraps: int
    meters: float


def pompom(gauge: Gauge, diameter_cm: float) -> Pompom:
    """Pompon de `diameter_cm` con un molde de anillo (agujero de 1/3).

    ASUNCION: diametro del hilo = 0,5 / pts por cm (coincide con las vueltas
    por pulgada del CYC: DK ~11, worsted ~9, bulky ~7). Hilo necesario =
    volumen de la esfera x relleno / seccion del hilo; cada vuelta alrededor
    del molde gasta ~0,7 x diametro.
    """
    thread = 0.5 / gauge.stitches_per_cm
    volume = math.pi / 6 * diameter_cm**3 * POMPOM_FILL
    length_cm = volume / (math.pi * (thread / 2) ** 2)
    wraps = max(40, round_half_up(length_cm / (0.7 * diameter_cm)))
    meters = math.ceil(length_cm / 100)
    return Pompom(diameter_cm=diameter_cm, wraps=wraps, meters=float(meters))


# ---------------------------------------------------------------------------
# Patron.
# ---------------------------------------------------------------------------


def meta(spec: GarmentSpec, params: PatternParams, family: str, title_key: str) -> PatternMeta:
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


def materials(
    craft: Craft,
    spec: GarmentSpec,
    params: PatternParams,
    area_cm2: float,
    notions: tuple[str, ...],
    *,
    extra_meters: float = 0.0,
) -> Materials:
    meters, _ = estimate_yarn(area_cm2, params.peso_hilo)
    meters = max(10.0, meters + extra_meters)
    grams = float(round(meters / (METERS_PER_100G[params.peso_hilo] / 100.0)))
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    return Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=None if craft.crochet else params.aguja_mm or default_needle_mm(params.peso_hilo),
        hook_mm=(params.ganchillo_mm or default_hook_mm(params.peso_hilo))
        if craft.crochet
        else None,
        meters=meters,
        grams=grams,
        notions=notions,
        colors=colors,
    )


def common_warnings(craft: Craft, params: PatternParams) -> list[Warning]:
    warnings = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
    ]
    if craft.crochet:
        warnings.append(Warning("crochet_gauge", "warning.crochet_gauge", severity="info"))
    if params.medidas_cm or params.dimensiones_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    return warnings


def has_finish(spec: GarmentSpec, finish: Finish) -> bool:
    return finish in spec.acabados


@dataclass
class Parts:
    """Acumulador de secciones y medidas de un patron."""

    sections: list[Section] = field(default_factory=list)

    def add(self, section: Section) -> Section:
        self.sections.append(section)
        return section


def family_name(craft: Craft, family: str) -> str:
    return f"crochet_{family}" if craft.crochet else family


def gauge_of(params: PatternParams) -> Gauge:
    return resolve_gauge(params)


def pick_up(gauge: Gauge, rows: int) -> int:
    """Puntos a levantar a lo largo de `rows` hileras para que el borde mida
    lo mismo (en dos agujas da la regla clasica de 3 pts cada 4 hileras)."""
    return max(1, round_half_up(rows * gauge.stitches_per_cm / gauge.rows_per_cm))
