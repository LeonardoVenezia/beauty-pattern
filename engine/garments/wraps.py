"""Prendas de abrigo hechas con rectangulos: bolero, poncho y ruana.

- Bolero (`shrug`): un rectangulo de puno a puno, del ancho del contorno de
  brazo; se dobla a lo largo, se cosen los extremos (las mangas) y la abertura
  del medio lleva una tira levantada en redondo. Es la construccion de bolero
  mas difundida para principiantes, en agujas y en crochet.
- Poncho clasico: dos rectangulos iguales; el lado corto de cada uno se cose
  al lado largo del otro y queda la punta adelante y atras (poncho en V).
- Ruana: un rectangulo grande abierto adelante: espalda entera y, desde los
  hombros, dos delanteros separados por la abertura.

ASUNCIONES (docs/fuentes.md): holgura de la manga del bolero 6 cm, costura
de cada manga = 85 % de su largo, tira de 5 cm al 90 % del contorno de la
abertura; tablas de medidas de poncho y ruana por talle (adulto XS-3XL y
nino 2-12) y abertura del cuello = cabeza + 4 cm. Bordes en santa clara (no
se enrulan) salvo que la foto muestre otro punto que tampoco se enrula.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.garments.base import ImpossibleProportionsError
from engine.garments.options import SLEEVE_FRACTION
from engine.gauge import Gauge, crochet_gauge
from engine.i18n import t
from engine.ir import (
    CountRef,
    JoinCheck,
    Materials,
    Measurement,
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
from engine.sizes import ease_for_fit, resolve_body_size
from engine.spec import (
    GarmentSpec,
    PatternParams,
    PonchoStyle,
    SleeveLength,
    Technique,
    resolve_gauge,
)
from engine.stitches.catalog import adjust_stitches, catalog_id_for_name, expand_row, get_stitch
from engine.stitches.kinds import StitchKind

SHRUG_SLEEVE_EASE_CM = 6.0
SHRUG_SEAM_SHARE = 0.85
EDGING_CM = 5.0
EDGING_SHARE = 0.9
CUFF_CM = 4.0
# Puntos de dos agujas que no se enrulan (sirven sin borde aparte).
_FLAT_KNIT = {"garter", "seed", "moss", "rib_1x1", "rib_2x2", "basketweave", "broken_rib"}
_CROCHET_IDS = {"crochet_sc", "crochet_hdc", "crochet_dc"}

# Poncho clasico: ancho de cada rectangulo (cm) y contorno de cabeza (cm).
# ASUNCION: el ancho es el largo del poncho desde el hombro; cabeza segun
# tablas de talles de gorros (CYC "Head circumference"), redondeada.
PONCHO_SIZES: dict[str, tuple[float, float]] = {
    "2": (26.0, 49.0),
    "4": (30.0, 50.0),
    "6": (33.0, 51.0),
    "8": (36.0, 52.0),
    "10": (39.0, 53.0),
    "12": (42.0, 54.0),
    "XS": (44.0, 55.0),
    "S": (46.0, 56.0),
    "M": (48.0, 56.0),
    "L": (50.0, 57.0),
    "XL": (52.0, 57.0),
    "2XL": (54.0, 58.0),
    "3XL": (56.0, 58.0),
}
# Ruana: ancho total (de muneca a muneca con los brazos abiertos a medias) y
# largo de la espalda (del hombro al borde). ASUNCION a partir de ruanas
# publicadas (adulto ~130 x 75 cm).
RUANA_SIZES: dict[str, tuple[float, float]] = {
    "2": (70.0, 40.0),
    "4": (78.0, 45.0),
    "6": (86.0, 50.0),
    "8": (94.0, 54.0),
    "10": (102.0, 58.0),
    "12": (110.0, 62.0),
    "XS": (120.0, 70.0),
    "S": (124.0, 72.0),
    "M": (128.0, 74.0),
    "L": (132.0, 76.0),
    "XL": (136.0, 78.0),
    "2XL": (140.0, 80.0),
    "3XL": (144.0, 82.0),
}
NECK_OPENING_EASE_CM = 4.0


def _stitch_id(spec: GarmentSpec, crochet: bool) -> tuple[str, bool]:
    """(punto, se cambio el de la foto). Agujas: santa clara salvo un punto
    que no se enrula; crochet: el de la foto o medio punto alto."""
    wanted = catalog_id_for_name(spec.punto_base) if spec.punto_base else None
    if crochet:
        if wanted in _CROCHET_IDS:
            return str(wanted), False
        return "crochet_hdc", wanted is not None
    if wanted in _FLAT_KNIT:
        return str(wanted), False
    return "garter", wanted not in {None, "stockinette", "garter"}


def _params(params: PatternParams, stitch: str, crochet: bool) -> PatternParams:
    if not crochet or params.densidad is not None:
        return params
    return params.model_copy(update={"densidad": crochet_gauge(params.peso_hilo.value, stitch)})


def _rows(
    stitch: str,
    stitches: int,
    count: int,
    first: int,
    *,
    crochet: bool,
    start: bool,
    note: str | None,
) -> list[Step]:
    """Montaje (o cadena) opcional y `count` hileras del punto."""
    pattern = get_stitch(stitch)
    steps: list[Step] = []
    number = first
    if start:
        kind = StitchKind.CH if crochet else StitchKind.CAST_ON
        foundation = "pattern.note.crochet_foundation" if crochet else "pattern.note.cast_on_panel"
        steps.append(build_step(number, 0, (Op(kind, times=stitches),), note_key=foundation))
        number += 1
    for index in range(count):
        steps.append(
            build_step(number, stitches, expand_row(pattern, stitches, index + 1), note_key=note if index == 0 else None)
        )
        number += 1
    return steps


def _meta(spec: GarmentSpec, params: PatternParams, family: str, title_key: str, size: str) -> PatternMeta:
    digest = hashlib.sha256((spec.model_dump_json() + params.model_dump_json() + family).encode()).hexdigest()[:12]
    return PatternMeta(
        id=digest,
        family=family,
        title_key=title_key,
        size=size,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )


def _materials(spec: GarmentSpec, params: PatternParams, area: float, crochet: bool) -> Materials:
    meters, grams = estimate_yarn(area, params.peso_hilo)
    notions = ("notion.crochet_hook" if crochet else "notion.row_counter", "notion.tapestry_needle", "notion.tape_measure")
    return Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=None if crochet else params.aguja_mm or default_needle_mm(params.peso_hilo),
        hook_mm=(params.ganchillo_mm or default_hook_mm(params.peso_hilo)) if crochet else None,
        meters=meters,
        grams=grams,
        notions=notions,
        colors=tuple(spec.colorwork.paleta) if spec.colorwork else (),
    )


def _warnings(params: PatternParams, stitch: str, changed: bool, crochet: bool) -> list[Warning]:
    warnings = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
    ]
    if crochet:
        warnings.append(Warning("crochet_gauge", "warning.crochet_gauge", severity="info"))
    if changed:
        warnings.append(
            Warning(
                "wrap_stitch",
                "garments.warning.wrap_stitch",
                params={"stitch": t(get_stitch(stitch).name_key, params.idioma)},
            )
        )
    if params.medidas_cm or params.dimensiones_cm:
        warnings.append(Warning("custom_measurements", "warning.custom_measurements", severity="info"))
    return warnings


# ---------------------------------------------------------------------------
# Bolero
# ---------------------------------------------------------------------------


def _shrug(spec: GarmentSpec, params: PatternParams, *, crochet: bool) -> Pattern:
    stitch, changed = _stitch_id(spec, crochet)
    params = _params(params, stitch, crochet)
    gauge = resolve_gauge(params)
    size = resolve_body_size(params.talla, params.medidas_cm)
    multiple = get_stitch(stitch).multiple
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    kind = spec.largo_manga or SleeveLength.ELBOW  # ASUNCION: bolero con manga al codo
    if kind is SleeveLength.SLEEVELESS:
        sleeve_cm = 12.0  # apenas cubre el hombro
    else:
        sleeve_cm = size.sleeve_length_cm * SLEEVE_FRACTION[kind]
    width_cm = size.upper_arm_cm + SHRUG_SLEEVE_EASE_CM + max(0.0, ease - 6.0) / 4
    back_cm = size.cross_back_cm
    length_cm = back_cm + 2 * sleeve_cm
    stitches = adjust_stitches(max(multiple, round_half_up(width_cm * gauge.stitches_per_cm)), multiple)
    if crochet:
        cuff_rows = 0
        body_rows = max(4, gauge.rows_for_cm(length_cm))
    else:
        cuff_rows = max(2, gauge.rows_for_cm(CUFF_CM))
        body_rows = max(4, gauge.rows_for_cm(length_cm) - 2 * cuff_rows)
    steps: list[Step] = []
    if crochet:
        steps = _rows(stitch, stitches, body_rows, 1, crochet=True, start=True, note="garments.note.shrug_body")
    else:
        # Puno, cuerpo y puno en una sola pieza (el elastico va en 2x2 sobre
        # un multiplo de 4; el resto, en el punto del cuerpo).
        rib = "rib_2x2" if stitches % 4 == 0 else "rib_1x1" if stitches % 2 == 0 else stitch
        steps = _rows(rib, stitches, cuff_rows, 1, crochet=False, start=True, note="garments.note.shrug_cuff")
        steps += _rows(stitch, stitches, body_rows, len(steps) + 1, crochet=False, start=False, note="garments.note.shrug_body")
        steps += _rows(rib, stitches, cuff_rows, len(steps) + 1, crochet=False, start=False, note="garments.note.shrug_cuff_top")
    total_rows = len(steps) - 1
    real_length = gauge.cm_for_rows(total_rows)
    seam_cm = SHRUG_SEAM_SHARE * sleeve_cm
    opening_cm = 2 * (real_length - 2 * seam_cm)
    edging = 2 * max(4, round_half_up(EDGING_SHARE * opening_cm * gauge.stitches_per_cm / 2))
    edge_rows = max(2, gauge.rows_for_cm(EDGING_CM if not crochet else EDGING_CM / 2))
    if opening_cm <= 0:
        raise ImpossibleProportionsError("error.impossible_proportions", yoke=0, body=back_cm, sleeve=sleeve_cm)
    if crochet:
        edge_kind = StitchKind.SC
        edge_steps = [
            build_step(n, edging, (Op(edge_kind, times=edging),), note_key="garments.note.shrug_edging_crochet" if n == 1 else None)
            for n in range(1, edge_rows + 1)
        ]
    else:
        edge_rib = get_stitch("rib_1x1")
        edge_steps = [
            build_step(
                n,
                edging,
                expand_row(edge_rib, edging, n, in_the_round=True),
                note_key="garments.note.shrug_edging" if n == 1 else None,
            )
            for n in range(1, edge_rows + 1)
        ]
    body = Section(
        id="shrug",
        name_key="garments.section.shrug",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=stitches,
        target=SectionTarget("shrug_length", length_cm, max(1.5, gauge.cm_for_rows(2)), "length"),
        meta={"row_count": total_rows, "cast_on": stitches, "seam_rows": gauge.rows_for_cm(seam_cm)},
        bind_off=True,
    )
    edge = Section(
        id="edging",
        name_key="garments.section.shrug_edging",
        mode="round",
        steps=tuple(edge_steps),
        start_stitches=edging,
        end_stitches=edging,
        meta={"row_count": edge_rows, "picked_up": edging},
        bind_off=True,
    )
    tol = max(2.5, 2 * gauge.cm_for_stitches(multiple))
    measurements = (
        Measurement("length", real_length, length_cm, max(1.5, gauge.cm_for_rows(2)), "length"),
        Measurement("upper_arm", gauge.cm_for_stitches(stitches), width_cm, tol, "circumference"),
        Measurement("cross_back", back_cm, None, kind="width"),
        Measurement("sleeve_length", seam_cm, None, kind="length"),
    )
    area = gauge.cm_for_stitches(stitches) * real_length + opening_cm * (EDGING_CM if not crochet else EDGING_CM / 2)
    family = "crochet_shrug" if crochet else "shrug"
    return Pattern(
        meta=_meta(spec, params, family, f"title.{family}", size.key),
        spec=spec,
        params=params,
        sections=(body, edge),
        measurements=measurements,
        materials=_materials(spec, params, area, crochet),
        warnings=tuple(_warnings(params, stitch, changed, crochet)),
    )


def generate_shrug(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _shrug(spec, params, crochet=False)


def generate_crochet_shrug(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _shrug(spec, params, crochet=True)


# ---------------------------------------------------------------------------
# Poncho y ruana
# ---------------------------------------------------------------------------


def _size_key(talla: str, table: dict[str, tuple[float, float]]) -> str:
    key = talla.strip().upper()
    if key not in table:
        valid = ", ".join(table)
        raise ValueError(f"talle desconocido {talla!r}; talles: {valid}")
    return key


def _poncho(spec: GarmentSpec, params: PatternParams, *, crochet: bool) -> Pattern:
    stitch, changed = _stitch_id(spec, crochet)
    params = _params(params, stitch, crochet)
    gauge = resolve_gauge(params)
    multiple = get_stitch(stitch).multiple
    if spec.estilo_poncho is PonchoStyle.RUANA:
        return _ruana(spec, params, gauge, stitch, changed, crochet=crochet)
    key = _size_key(params.talla, PONCHO_SIZES)
    width_cm, head_cm = PONCHO_SIZES[key]
    width_cm = params.dimensiones_cm.get("width", width_cm)
    opening_cm = head_cm + NECK_OPENING_EASE_CM
    length_cm = params.dimensiones_cm.get("length", width_cm + opening_cm / 2)
    if length_cm - width_cm < opening_cm / 2 - 0.01:
        raise ImpossibleProportionsError("error.impossible_proportions", yoke=0, body=width_cm, sleeve=length_cm)
    stitches = adjust_stitches(max(multiple, round_half_up(width_cm * gauge.stitches_per_cm)), multiple)
    rows = max(4, gauge.rows_for_cm(length_cm))
    steps = _rows(stitch, stitches, rows, 1, crochet=crochet, start=True, note="garments.note.poncho_rectangle")
    piece = Section(
        id="poncho_rectangle",
        name_key="garments.section.poncho_rectangle",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=stitches,
        target=SectionTarget("poncho_length", length_cm, max(1.0, gauge.cm_for_rows(2)), "length"),
        meta={"row_count": rows, "cast_on": stitches, "pieces": 2},
        bind_off=True,
    )
    real_w, real_l = gauge.cm_for_stitches(stitches), gauge.cm_for_rows(rows)
    tol = max(2.0, gauge.cm_for_stitches(multiple))
    measurements = (
        Measurement("width", real_w, width_cm, tol, "width"),
        Measurement("length", real_l, length_cm, max(1.0, gauge.cm_for_rows(2)), "length"),
        Measurement("neck", 2 * (real_l - real_w), opening_cm, 2 * tol + 2.0, "circumference"),
    )
    family = "crochet_poncho" if crochet else "poncho"
    return Pattern(
        meta=_meta(spec, params, family, f"title.{family}", key),
        spec=spec,
        params=params,
        sections=(piece,),
        measurements=measurements,
        materials=_materials(spec, params, 2 * real_w * real_l, crochet),
        warnings=tuple(_warnings(params, stitch, changed, crochet)),
    )


def _ruana(
    spec: GarmentSpec, params: PatternParams, gauge: Gauge, stitch: str, changed: bool, *, crochet: bool
) -> Pattern:
    key = _size_key(params.talla, RUANA_SIZES)
    width_cm, length_cm = RUANA_SIZES[key]
    width_cm = params.dimensiones_cm.get("width", width_cm)
    length_cm = params.dimensiones_cm.get("length", length_cm)
    multiple = get_stitch(stitch).multiple
    half = adjust_stitches(max(multiple, round_half_up(width_cm / 2 * gauge.stitches_per_cm)), multiple)
    total = 2 * half
    rows = max(4, gauge.rows_for_cm(length_cm))
    back_steps = _rows(stitch, total, rows, 1, crochet=crochet, start=True, note="garments.note.ruana_back")
    back = Section(
        id="back",
        name_key="section.back",
        mode="flat",
        steps=tuple(back_steps),
        start_stitches=0,
        end_stitches=total,
        target=SectionTarget("back_length", length_cm, max(1.0, gauge.cm_for_rows(2)), "length"),
        meta={"row_count": rows, "cast_on": total},
    )
    fronts = []
    for side, note in (("right", "garments.note.ruana_front_first"), ("left", "garments.note.ruana_front_second")):
        steps = _rows(stitch, half, rows, 1, crochet=crochet, start=False, note=note)
        fronts.append(
            Section(
                id=f"{side}_front",
                name_key=f"section.{side}_front",
                mode="flat",
                steps=tuple(steps),
                start_stitches=half,
                end_stitches=half,
                target=SectionTarget(f"{side}_front_length", length_cm, max(1.0, gauge.cm_for_rows(2)), "length"),
                meta={"row_count": rows},
                bind_off=True,
            )
        )
    joins = (
        JoinCheck(
            label_key="join.neck_split",
            left=(CountRef("back", "end"),),
            right=(CountRef("right_front", "start"), CountRef("left_front", "start")),
        ),
    )
    real_w = gauge.cm_for_stitches(total)
    tol = max(2.0, gauge.cm_for_stitches(2 * multiple))
    measurements = (
        Measurement("width", real_w, width_cm, tol, "width"),
        Measurement("length", gauge.cm_for_rows(rows), length_cm, max(1.0, gauge.cm_for_rows(2)), "length"),
    )
    family = "crochet_ruana" if crochet else "ruana"
    return Pattern(
        meta=_meta(spec, params, family, f"title.{family}", key),
        spec=spec,
        params=params,
        sections=(back, *fronts),
        measurements=measurements,
        materials=_materials(spec, params, 2 * real_w * gauge.cm_for_rows(rows), crochet),
        warnings=tuple(_warnings(params, stitch, changed, crochet)),
        joins=joins,
    )


def generate_poncho(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _poncho(spec, params, crochet=spec.tecnica is Technique.CROCHET)


def generate_crochet_poncho(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _poncho(spec, params, crochet=True)

