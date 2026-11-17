"""Documento de patron con la estructura del estandar de mercado.

Arma, a partir de los patrones verificados de cada talle, las 14 secciones de
la especificacion ("Especificacion generador de patrones de tejido"): portada,
descripcion, ficha tecnica, tabla de talles, materiales, muestra,
abreviaturas, puntos especiales, notas, instrucciones, graficos, esquema,
terminacion y creditos. Las secciones opcionales sin datos se omiten.

Todo numero sale de la IR de cada talle; las instrucciones de varios talles se
combinan con `engine.multisize` (notacion `a (b, c)`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine import ENGINE_VERSION
from engine.blocks import (
    Block,
    BlockKind,
    finishing_blocks,
    glossary_blocks,
    instruction_blocks,
)
from engine.colorwork import ColorworkChart, color_name
from engine.garments.panels import build_panel, panel_for, texture_motif
from engine.i18n import has_key, t
from engine.ir import Pattern, Step
from engine.multisize import format_values, merge_size_blocks, size_note
from engine.rounding import round_half_up
from engine.sizes import BODY_SIZES
from engine.spec import Technique, YarnWeight, resolve_gauge
from engine.stitches.catalog import StitchPattern
from engine.stitches.kinds import StitchKind

# Craft Yarn Council, Standard Yarn Weight System (verificado 2026-11-11).
CYC_CATEGORY: dict[YarnWeight, int] = {
    YarnWeight.LACE: 0,
    YarnWeight.FINGERING: 1,
    YarnWeight.SPORT: 2,
    YarnWeight.DK: 3,
    YarnWeight.WORSTED: 4,
    YarnWeight.BULKY: 5,
    YarnWeight.SUPER_BULKY: 6,
}

# Craft Yarn Council, Hooks and Needles (verificado 2026-11-11). Solo los
# tamanos con equivalencia publicada; el resto se da solo en mm.
US_NEEDLE: dict[float, str] = {
    1.5: "000", 1.75: "00", 2.0: "0", 2.25: "1", 2.75: "2", 3.25: "3",
    3.5: "4", 3.75: "5", 4.0: "6", 4.5: "7", 5.0: "8", 5.5: "9", 6.0: "10",
    6.5: "10.5", 8.0: "11", 9.0: "13", 10.0: "15", 12.75: "17", 15.0: "19",
}
US_HOOK: dict[float, str] = {
    2.25: "B-1", 2.75: "C-2", 3.25: "D-3", 3.5: "E-4", 3.75: "F-5", 4.0: "G-6",
    4.5: "7", 5.0: "H-8", 5.5: "I-9", 6.0: "J-10", 6.5: "K-10.5", 8.0: "L-11",
    9.0: "M/N-13", 10.0: "N/P-15", 11.5: "P-16", 15.0: "P/Q",
}

_GARMENTS = {"raglan_top_down", "yoke", "set_in", "drop_shoulder", "cardigan", "vest"}
_SIZED = _GARMENTS | {"crochet_pullover", "crochet_cardigan", "crochet_vest"}
_LACE_CABLE = {StitchKind.YO, StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}
_SHAPING = {
    StitchKind.M1L, StitchKind.M1R, StitchKind.KFB, StitchKind.K2TOG, StitchKind.SSK,
    StitchKind.P2TOG, StitchKind.SSP, StitchKind.CROCHET_INC, StitchKind.CROCHET_DEC,
    StitchKind.GRANNY_CORNER,
}


@dataclass(frozen=True)
class PatternDocument:
    title: str
    subtitle: str
    sizes: tuple[str, ...]
    highlight: int | None  # indice del talle resaltado, o None
    blocks: tuple[Block, ...]
    schematic: Pattern  # talle cuyo esquema se dibuja
    version: str
    date: str
    language: str
    charts: tuple[StitchPattern, ...] = ()
    # Graficos de jacquard (BlockKind.COLORWORK_CHART) y su paleta (#rrggbb).
    colorwork_charts: tuple[ColorworkChart, ...] = ()
    palette: tuple[str, ...] = ()


def _kinds(patterns: list[Pattern]) -> set[StitchKind]:
    kinds: set[StitchKind] = set()
    for pattern in patterns:
        for section in pattern.sections:
            for step in section.steps:
                kinds.update(op.kind for op in step.expanded_ops())
    return kinds


def cyc_level(patterns: list[Pattern]) -> int:
    """Nivel CYC derivado de las tecnicas que el patron realmente usa.

    1 principiante: puntos basicos, sin forma, piezas planas.
    2 facil: aumentos y disminuciones sencillos o tejido en redondo simple.
    3 intermedio: calados o trenzas, o prenda con forma tejida en redondo.
    4 avanzado: jacquard o intarsia.
    """
    base = patterns[0]
    kinds = _kinds(patterns)
    colorwork = base.spec.colorwork
    if colorwork and colorwork.tipo.value in {"fair_isle", "intarsia", "mosaic"}:
        return 4
    if kinds & _LACE_CABLE:
        return 3
    if base.meta.family in _GARMENTS:
        return 3
    if kinds & _SHAPING or any(s.mode == "round" for s in base.sections):
        return 2
    return 1


def _techniques(patterns: list[Pattern], lang: str) -> list[str]:
    base = patterns[0]
    kinds = _kinds(patterns)
    found: list[str] = []
    if any(s.mode == "round" for s in base.sections):
        found.append("technique.in_the_round")
    if kinds & {StitchKind.M1L, StitchKind.M1R}:
        found.append("technique.increases")
    elif StitchKind.KFB in kinds:
        found.append("technique.increases_kfb")
    if kinds & {StitchKind.SSK, StitchKind.SSP}:
        found.append("technique.decreases")
    elif kinds & {StitchKind.K2TOG, StitchKind.P2TOG}:
        found.append("technique.decreases_k2tog")
    if any(s.division for s in base.sections):
        found.append("technique.hold_and_cast_on")
    if kinds & {StitchKind.MAGIC_RING, StitchKind.GRANNY_START}:
        found.append("technique.magic_ring")
    if kinds & {StitchKind.GRANNY_CORNER, StitchKind.GRANNY_SIDE}:
        found.append("technique.work_into_spaces")
    if kinds & {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}:
        found.append("technique.cables")
    if StitchKind.YO in kinds:
        found.append("technique.lace")
    if StitchKind.BOBBLE in kinds:
        found.append("technique.bobbles")
    if base.materials.colors and len(base.materials.colors) > 1:
        found.append("technique.color_changes")
    if base.finishing and base.meta.family == "amigurumi":
        found.append("technique.toy_assembly")
    return [t(key, lang) for key in found]


def _needle_text(mm: float, *, hook: bool, lang: str) -> str:
    table = US_HOOK if hook else US_NEEDLE
    us = table.get(mm)
    key = "pattern.hook" if hook else "pattern.needles"
    text = t(key, lang, mm=f"{mm:g}")
    return f"{text} (US {us})" if us else text


def _half(value: float) -> str:
    return f"{round_half_up(value * 2) / 2:g}"


def _length(value_cm: float, units: str) -> str:
    if units == "in":
        return f"{_half(value_cm / 2.54)}"
    return _half(value_cm)


def _merged(values: list[str]) -> str:
    return format_values(tuple(values))


def growth_rounds(steps: tuple[Step, ...]) -> list[Step]:
    """Las vueltas del principio mientras la pieza crece."""
    grow = list(steps[:1])
    for step in steps[1:]:
        if step.stitch_count_end <= grow[-1].stitch_count_end:
            break
        grow.append(step)
    return grow


def _round_chart_pieces(pattern: Pattern, lang: str) -> list[str]:
    """Piezas que se tejen exactamente como el dibujo (el de la primera):
    mismas vueltas de aumento, en orden, y sin volver a aumentar despues."""
    chart = [step.items for step in growth_rounds(pattern.sections[0].steps)]
    names: list[str] = []
    for section in pattern.sections:
        grow = growth_rounds(section.steps)
        same = [step.items for step in grow] == chart[: len(grow)]
        if same and max(s.stitch_count_end for s in section.steps) == grow[-1].stitch_count_end:
            name = t(section.name_key, lang)
            if name not in names:
                names.append(name)
    return names


def build_document(
    patterns: list[Pattern],
    *,
    highlight: str | None = None,
    lang: str | None = None,
    today: date | None = None,
) -> PatternDocument:
    """Documento completo. `patterns`: un patron verificado por talle."""
    if not patterns:
        raise ValueError("se necesita al menos un patron")
    base = patterns[0]
    language = lang or base.params.idioma
    units = base.params.unidades
    unit = t(f"unit.{units}", language)
    multi = len(patterns) > 1
    sizes = [p.meta.size for p in patterns]
    title = t(base.meta.title_key, language)
    is_crochet = base.spec.tecnica is Technique.CROCHET
    blocks: list[Block] = []

    def heading(key: str) -> None:
        blocks.append(Block(BlockKind.DOC_HEADING, t(key, language)))

    def line(text: str) -> None:
        blocks.append(Block(BlockKind.LINE, text))

    # 1a. Esquema.
    heading("pattern.schematic")
    chosen = sizes.index(highlight) if highlight in sizes else (len(sizes) // 2 if multi else 0)
    blocks.append(Block(BlockKind.SCHEMATIC, sizes[chosen]))
    if multi:
        line(t("doc.schematic_note", language, size=sizes[chosen]))

    # 1b. Graficos (arriba de todo: la mejor entrada).
    charts: list[StitchPattern] = []
    body = next((s for s in base.sections if "panel_rows" in s.meta), None)
    if body is not None:
        motif = texture_motif(base.spec)
        if body.division:
            panel = panel_for(base.spec, body.division)
        else:
            panel = build_panel(motif, body.meta["panel_segment"]) if motif else None
        if panel is not None:
            charts.append(panel.chart())
            heading("doc.charts")
            blocks.append(Block(BlockKind.CHART, "0"))
            line(
                t(
                    "doc.chart_note_flat" if body.mode == "flat" else "doc.chart_note",
                    language,
                    n=1,
                    name=t(charts[0].name_key, language),
                    rows=panel.rows,
                )
            )
    colorwork: list[ColorworkChart] = []
    if base.meta.family == "yoke":
        from engine.garments.yoke import yoke_bands

        colorwork = [band.chart for band in yoke_bands(base.spec, base.params)]
    # Amigurumi al crochet: el dibujo de los aumentos (donde va cada punto).
    if base.meta.family == "amigurumi" and is_crochet and base.sections:
        heading("doc.charts")
        blocks.append(Block(BlockKind.ROUND_CHART, base.sections[0].id))
        line(t("doc.round_chart_note", language, pieces=", ".join(_round_chart_pieces(base, language))))
    if colorwork and not charts:
        heading("doc.charts")
    for index, chart in enumerate(colorwork):
        blocks.append(Block(BlockKind.COLORWORK_CHART, str(index)))
        line(
            t(
                "doc.colorwork_chart_note",
                language,
                n=chart.number,
                name=t(f"colorwork.motif.{chart.motif}", language),
                w=chart.width,
                rows=chart.height,
                bg=chr(65 + chart.background),
                fg=chr(65 + chart.contrast),
            )
        )

    # 2. Descripcion.
    heading("doc.description")
    is_ball = any(section.id == "ball" for section in base.sections)
    desc_key = "desc.toy_ball" if is_ball else "desc." + base.meta.title_key.removeprefix("title.")
    line(t(desc_key if has_key(desc_key, language) else "desc.generic", language))

    # 3. Ficha tecnica.
    heading("doc.technical")
    level = cyc_level(patterns)
    rows: list[tuple[str, ...]] = [
        (t("doc.level", language), f"{level} \u2013 {t(f'level.{level}', language)}"),
        (t("doc.technique", language), t(f"technique_name.{base.spec.tecnica.value}", language)),
    ]
    if base.meta.family in _SIZED:
        rows.append((t("doc.sizes", language), ", ".join(sizes)))
        bust = next((m for m in base.measurements if m.key == "bust"), None)
        if bust is not None:
            ease = bust.value_cm - BODY_SIZES[base.meta.size].bust_cm if base.meta.size in BODY_SIZES else None
            if ease is not None:
                rows.append((t("doc.ease", language), t("doc.ease_value", language, cm=_half(ease))))
    toy_height = next((m for m in base.measurements if m.key == "toy_height"), None)
    if toy_height is not None:
        size_key = "doc.toy_size_value_ball" if is_ball else "doc.toy_size_value"
        size = t(size_key, language, n=_length(toy_height.value_cm, units), unit=unit)
        rows.append((t("doc.toy_size", language), size))
    techniques = _techniques(patterns, language)
    if techniques:
        rows.append((t("doc.techniques", language), ", ".join(techniques)))
    blocks.append(Block(BlockKind.TABLE, "", rows=tuple(rows)))

    # 4. Tabla de talles y medidas (prendas).
    if multi:
        heading("doc.size_table")
        header = (t("doc.measure", language) + f" ({unit})", *sizes)
        table: list[tuple[str, ...]] = [header]
        body_row = [
            _length(BODY_SIZES[s].bust_cm, units) if s in BODY_SIZES else "\u2013" for s in sizes
        ]
        table.append((t("doc.body_bust", language), *body_row))
        for index, measurement in enumerate(base.measurements):
            letter = chr(65 + index)
            values = [_length(p.measurements[index].value_cm, units) for p in patterns]
            label = f"{letter}. {t(f'measure.{measurement.key}', language)}"
            table.append((label, *values))
        blocks.append(Block(BlockKind.TABLE, "", rows=tuple(table)))
        line(t("doc.size_choice", language))

    # 5. Materiales.
    heading("doc.materials")
    weight = base.materials.yarn_weight
    category = CYC_CATEGORY.get(weight)
    yarn = t(f"yarn.{weight.value}", language)
    if category is not None:
        yarn = t("doc.yarn_cyc", language, name=yarn, n=category)
    line(t("doc.yarn", language, yarn=yarn))
    meters = _merged([f"{p.materials.meters:g}" for p in patterns])
    if base.materials.grams is not None:
        grams = _merged([f"{p.materials.grams or 0:g}" for p in patterns])
        line(t("pattern.yardage", language, m=meters, g=grams))
    else:
        line(t("pattern.yardage_no_grams", language, m=meters))
    if base.materials.needle_mm is not None:
        line(_needle_text(base.materials.needle_mm, hook=False, lang=language))
    if base.materials.hook_mm is not None:
        line(_needle_text(base.materials.hook_mm, hook=True, lang=language))
    if base.materials.notions:
        notions = ", ".join(t(key, language) for key in base.materials.notions)
        line(f"{t('pattern.notions', language)}: {notions}")
    if base.materials.colors:
        colors = ", ".join(
            f"{chr(65 + i)}: {color_name(c, language)} ({c})" if c.startswith("#") else f"{chr(65 + i)}: {c}"
            for i, c in enumerate(base.materials.colors)
        )
        line(t("doc.colors", language, colors=colors))
    if base.materials.color_meters and all(
        len(p.materials.color_meters) == len(base.materials.color_meters) for p in patterns
    ):
        per_color = [
            f"{chr(65 + i)} {_merged([f'{p.materials.color_meters[i]:g}' for p in patterns])} m"
            for i in range(len(base.materials.color_meters))
            if base.materials.color_meters[i]
        ]
        line(t("doc.color_meters", language, colors="; ".join(per_color)))

    # 6. Muestra.
    heading("doc.gauge")
    gauge = resolve_gauge(base.params)
    tool = base.materials.hook_mm if is_crochet else base.materials.needle_mm
    stitch_key = "doc.gauge_stitch_crochet" if is_crochet else "doc.gauge_stitch_knit"
    if base.meta.family == "crochet_motif":  # el motor mide el motivo en pb
        stitch_key = "doc.gauge_stitch_sc"
    if any(s.meta.get("garter_gauge") for s in base.sections):  # hogar: punto bobo
        stitch_key = "doc.gauge_stitch_garter"
    stitch = t(stitch_key, language)
    line(
        t(
            "doc.gauge_line",
            language,
            sts=_half(gauge.stitches_per_10cm),
            rows=_half(gauge.rows_per_10cm),
            stitch=stitch,
            tool=t("doc.hook" if is_crochet else "doc.needle", language, mm=f"{tool or 0:g}"),
        )
    )
    if base.meta.family == "granny_square":
        rounds_cm = 2 * 3 / gauge.rows_per_cm
        line(t("doc.gauge_granny", language, cm=_half(rounds_cm)))
    line(t("doc.gauge_why_crochet" if is_crochet else "doc.gauge_why", language))

    # 7. Abreviaturas (union de todos los talles, en orden alfabetico).
    glossary: list[Block] = []
    for pattern in patterns:
        for block in glossary_blocks(pattern, language):
            if block not in glossary:
                glossary.append(block)
    if glossary:
        heading("pattern.abbreviations")
        head, rest = glossary[0], sorted(glossary[1:], key=lambda b: (b.label or "").casefold())
        blocks.append(
            Block(
                BlockKind.TABLE,
                "",
                rows=tuple((b.label or "", b.value or "") for b in [head, *rest]),
            )
        )

    # 9. Notas del patron.
    heading("pattern.notes")
    construction_key = "construction." + base.meta.family
    if has_key(construction_key, language):
        line(t(construction_key, language))
    if multi:
        line(size_note(sizes, language))
    line(t("doc.yarn_substitution", language))
    seen: set[str] = set()
    for pattern in patterns:
        for warning in pattern.warnings:
            text = t(warning.message_key, language, **warning.params)
            if text not in seen:
                seen.add(text)
                blocks.append(Block(BlockKind.WARNING, text))

    # 10. Instrucciones.
    heading("pattern.instructions")
    per_size = [instruction_blocks(p, language) for p in patterns]
    blocks.extend(merge_size_blocks(per_size, sizes, language) if multi else per_size[0])

    # 13. Terminacion.
    heading("pattern.finished")
    finishing_key = "finishing." + base.meta.family
    if has_key(finishing_key, language):
        line(t(finishing_key, language))
    blocks.extend(finishing_blocks(base, language))
    toy = base.meta.family == "amigurumi"
    line(t("doc.weave_ends_toy" if toy else "doc.weave_ends", language))
    if not toy:
        line(t("pattern.block", language))

    when = (today or date.today()).isoformat()
    subtitle_parts = [t(f"technique_name.{base.spec.tecnica.value}", language)]
    if base.meta.family in _SIZED:
        subtitle_parts.append(t("doc.sizes_line", language, sizes=", ".join(sizes)))
    subtitle_parts.append(t("doc.level_short", language, n=level))
    return PatternDocument(
        title=title,
        subtitle=" · ".join(subtitle_parts),
        sizes=tuple(sizes),
        highlight=sizes.index(highlight) if multi and highlight in sizes else None,
        blocks=tuple(blocks),
        schematic=patterns[chosen],
        charts=tuple(charts),
        colorwork_charts=tuple(colorwork),
        palette=base.materials.colors,
        version=ENGINE_VERSION,
        date=when,
        language=language,
    )
