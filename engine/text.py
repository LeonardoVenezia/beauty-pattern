"""Texto determinista del patron a partir de la IR.

Siempre existe como respaldo del redactor de IA: no agrega ni cambia numeros.
"""

from __future__ import annotations

from engine.i18n import has_key, t
from engine.ir import Item, Op, Pattern, Section, Step
from engine.spec import Technique, resolve_gauge
from engine.stitches.kinds import StitchKind

_GARMENT_FAMILIES = {
    "raglan_top_down",
    "drop_shoulder",
    "yoke",
    "set_in_sleeve",
    "cardigan",
    "vest",
}


def _length(value_cm: float, units: str, lang: str) -> tuple[str, str]:
    if units == "in":
        return f"{value_cm / 2.54:.1f}", t("unit.in", lang)
    return f"{value_cm:.1f}", t("unit.cm", lang)


def _op_text(op: Op, lang: str, level: str) -> str:
    suffix = "one" if op.times == 1 else "run"
    params: dict[str, object] = {
        "n": op.times,
        "width": op.width or 0,
        "half": (op.width or 0) // 2,
    }
    if level == "experta":
        expert_key = f"op.{op.kind.value}.expert.{suffix}"
        if has_key(expert_key, lang) or has_key(expert_key, "es"):
            return t(expert_key, lang, **params)
    return t(f"op.{op.kind.value}.{suffix}", lang, **params)


def _item_text(item: Item, lang: str, level: str) -> str:
    if isinstance(item, Op):
        return _op_text(item, lang, level)
    ops = ", ".join(_op_text(op, lang, level) for op in item.ops)
    return t("pattern.repeat_group", lang, n=item.times, ops=ops)


def format_step(step: Step, mode: str, lang: str, level: str) -> str:
    label = t("pattern.round" if mode == "round" else "pattern.row", lang, n=step.number)
    body = ", ".join(_item_text(item, lang, level) for item in step.items)
    count = t("pattern.stitch_count", lang, n=step.stitch_count_end)
    note = t(step.note_key, lang) + " " if step.note_key else ""
    return f"{note}{label}: {body} {count}"


def _section_intro(section: Section, lang: str) -> str:
    if section.steps:
        first_ops = section.steps[0].expanded_ops()
        cast_on = sum(op.times for op in first_ops if op.kind is StitchKind.CAST_ON)
        if cast_on:
            return t("pattern.cast_on", lang, n=cast_on)
        if any(op.kind is StitchKind.MAGIC_RING for op in first_ops):
            return t("pattern.magic_ring", lang)
        chains = sum(op.times for op in first_ops if op.kind is StitchKind.CH)
        if chains:
            return t("pattern.cast_on_crochet", lang, n=chains)
    if section.id == "neckband":
        return t("pattern.cast_on_round", lang, n=section.start_stitches)
    if section.id == "yoke":
        meta = section.meta
        return t(
            "pattern.yoke_summary",
            lang,
            back=meta.get("back_final", section.start_stitches),
            front=meta.get("front_final", section.start_stitches),
            sleeve=meta.get("sleeve_final", section.start_stitches),
        )
    if section.id == "body":
        meta = section.meta
        return t(
            "pattern.separation_summary",
            lang,
            body=meta.get("body", section.end_stitches),
            u=meta.get("underarm", 0),
            sleeve=meta.get("sleeve_final", 0),
        )
    if section.id == "hem":
        return t("pattern.hem_start", lang, n=section.start_stitches)
    if section.id.startswith("sleeve_"):
        return t("pattern.sleeve_start", lang, n=section.start_stitches)
    if section.id.startswith("cuff_"):
        return t("pattern.cuff_start", lang, n=section.start_stitches)
    return t("pattern.section_start", lang, n=section.start_stitches)


def render_pattern_text(
    pattern: Pattern,
    *,
    lang: str | None = None,
    level: str | None = None,
) -> str:
    language = lang or pattern.params.idioma
    difficulty = level or pattern.params.nivel
    gauge = resolve_gauge(pattern.params)
    lines: list[str] = [t(pattern.meta.title_key, language)]
    if pattern.meta.family in _GARMENT_FAMILIES:
        lines.append(t("pattern.size", language, size=pattern.meta.size))
    lines.extend(
        [
            t(
                "pattern.gauge",
                language,
                sts=f"{gauge.stitches_per_10cm:g}",
                rows=f"{gauge.rows_per_10cm:g}",
            ),
            "",
        ]
    )
    lines.extend(
        [
            t("pattern.materials", language),
            t(
                "pattern.yarn",
                language,
                weight=t(f"yarn.{pattern.materials.yarn_weight.value}", language),
            ),
        ]
    )
    if pattern.materials.needle_mm is not None:
        lines.append(
            t("pattern.needles", language, mm=f"{pattern.materials.needle_mm:g}")
        )
    if pattern.materials.hook_mm is not None:
        lines.append(t("pattern.hook", language, mm=f"{pattern.materials.hook_mm:g}"))
    if pattern.materials.grams is None:
        lines.append(
            t("pattern.yardage_no_grams", language, m=f"{pattern.materials.meters:g}")
        )
    else:
        lines.append(
            t(
                "pattern.yardage",
                language,
                m=f"{pattern.materials.meters:g}",
                g=f"{pattern.materials.grams:g}",
            )
        )
    if pattern.materials.notions:
        notions = ", ".join(t(key, language) for key in pattern.materials.notions)
        lines.append(f"{t('pattern.notions', language)}: {notions}")
    if pattern.materials.colors:
        lines.append(
            f"{t('color.main', language)}: {', '.join(pattern.materials.colors)}"
        )
    lines.append("")

    lines.append(t("pattern.finished_measurements", language))
    for measurement in pattern.measurements:
        value, unit = _length(measurement.value_cm, pattern.params.unidades, language)
        label = t(f"measure.{measurement.key}", language)
        lines.append(
            t(
                "pattern.measurement_line",
                language,
                label=label,
                value=value,
                unit=unit,
            )
        )
    lines.append("")

    if pattern.warnings:
        lines.append(t("pattern.notes", language))
        for warning in pattern.warnings:
            lines.append(f"- {t(warning.message_key, language, **warning.params)}")
        lines.append("")

    lines.append(t("pattern.instructions", language))
    for section in pattern.sections:
        lines.append("")
        lines.append(t(section.name_key, language))
        lines.append(_section_intro(section, language))
        for note_key in section.note_keys:
            lines.append(t(note_key, language))
        for step in section.steps:
            lines.append(format_step(step, section.mode, language, difficulty))
        if section.bind_off:
            bind_key = (
                "pattern.bind_off_crochet"
                if pattern.spec.tecnica is Technique.CROCHET
                else "pattern.bind_off"
            )
            if bind_key == "pattern.bind_off_crochet":
                lines.append(t(bind_key, language))
            else:
                lines.append(t(bind_key, language, n=section.end_stitches))

    lines.extend(
        [
            "",
            t("pattern.finished", language),
            t("pattern.block", language),
            t("pattern.sample_reminder", language),
        ]
    )
    return "\n".join(lines)
