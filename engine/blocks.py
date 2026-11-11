"""Bloques tipados del patron: la capa de presentacion que comparten el texto y el PDF.

La IR sigue siendo la unica fuente de los numeros; este modulo la convierte en
una lista de bloques deterministas (titulo, medidas, glosario, pasos comprimidos).
El texto plano y el PDF renderizan los mismos bloques, como el simulador y el
texto comparten la misma IR.

La compresion de vueltas es solo presentacional: no cambia conteos ni descarta
pasos. Cada bloque comprimido declara el conteo final implicado, y el contador
de la web sigue leyendo los pasos reales de la IR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from engine.i18n import has_key, t
from engine.ir import Item, Op, Pattern, Repeat, Section, Step
from engine.rounding import round_half_up
from engine.spec import resolve_gauge
from engine.stitches.kinds import StitchKind

_GARMENT_FAMILIES = {
    "raglan_top_down",
    "drop_shoulder",
    "yoke",
    "set_in_sleeve",
    "cardigan",
    "vest",
    "crochet_pullover",
    "crochet_cardigan",
    "crochet_vest",
}

# Puntos de relleno: sus repeticiones crecen o decrecen dentro de una progresion
# (por ejemplo, los derechos entre aumentos de raglan), asi que se enmascaran
# al comparar la "forma" de dos vueltas.
_FILLER_KINDS = {StitchKind.KNIT, StitchKind.PURL, StitchKind.SC, StitchKind.HDC, StitchKind.DC}

_MAX_CYCLE = 8  # el motivo mas largo del catalogo (nido de abeja) tiene 8 vueltas
_MIN_SAVINGS = 3


class BlockKind(Enum):
    """Tipo de bloque: define el estilo de render en texto y PDF."""

    TITLE = auto()
    SUBTITLE = auto()
    LINE = auto()
    DOC_HEADING = auto()
    SECTION_HEADING = auto()
    MEASURE = auto()
    GLOSSARY = auto()
    STEP = auto()
    REPEAT = auto()
    WARNING = auto()
    TABLE = auto()  # rows[0] es el encabezado
    SCHEMATIC = auto()  # lugar del esquema; el render inserta el dibujo
    CHART = auto()  # grafico de puntos; text = indice en PatternDocument.charts
    PAGE_BREAK = auto()


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str
    label: str | None = None
    value: str | None = None
    rows: tuple[tuple[str, ...], ...] = ()


# ---------------------------------------------------------------------------
# Formateo de operaciones (siempre abreviado; el glosario explica).
# ---------------------------------------------------------------------------


def _op_text(op: Op, lang: str) -> str:
    suffix = "one" if op.times == 1 else "run"
    params: dict[str, object] = {
        "n": op.times,
        "width": op.width or 0,
        "half": (op.width or 0) // 2,
    }
    expert_key = f"op.{op.kind.value}.expert.{suffix}"
    return t(expert_key, lang, **params)


def _item_text(item: Item, lang: str) -> str:
    if isinstance(item, Op):
        return _op_text(item, lang)
    ops = ", ".join(_op_text(op, lang) for op in item.ops)
    return t("pattern.repeat_group", lang, n=item.times, ops=ops)


_GRANNY_CLUSTERS = {
    StitchKind.GRANNY_START: 1,
    StitchKind.GRANNY_CORNER: 2,
    StitchKind.GRANNY_SIDE: 1,
}


def _granny_clusters(step: Step) -> int:
    return sum(_GRANNY_CLUSTERS.get(op.kind, 0) for op in step.expanded_ops())


def _raglan_parts(step: Step) -> tuple[bool, ...] | None:
    """Lee una vuelta de canesu raglan: 4 partes [m1l] d [m1r] + 2 d de raglan.

    Devuelve si cada parte aumenta, o None si la vuelta no tiene esa forma.
    """
    items = list(step.items)
    parts: list[bool] = []
    index = 0
    for _ in range(4):

        def at(i: int, kind: StitchKind) -> bool:
            item = items[i] if i < len(items) else None
            return isinstance(item, Op) and item.kind is kind

        inc_left = at(index, StitchKind.M1L)
        index += inc_left
        if not at(index, StitchKind.KNIT):
            return None
        index += 1
        inc_right = at(index, StitchKind.M1R)
        index += inc_right
        raglan = items[index] if index < len(items) else None
        if not (isinstance(raglan, Op) and raglan.kind is StitchKind.KNIT and raglan.times == 2):
            return None
        index += 1
        if inc_left != inc_right:
            return None
        parts.append(inc_left)
    if index != len(items) or not any(parts):
        return None
    return tuple(parts)


def _paired_decrease_text(step: Step, lang: str) -> str | None:
    """`1 der, ssk, N der, 2pjd, 1 der` -> `... der hasta quedar 3 pts ...`."""
    kinds = [
        (item.kind, item.times) if isinstance(item, Op) else None for item in step.items
    ]
    if kinds[:2] == [(StitchKind.KNIT, 1), (StitchKind.SSK, 1)] and kinds[3:] == [
        (StitchKind.K2TOG, 1),
        (StitchKind.KNIT, 1),
    ] and kinds[2] is not None and kinds[2][0] is StitchKind.KNIT:
        return t("pattern.paired_decrease", lang)
    return None


def _is_plain(step: Step) -> bool:
    only = step.items[0] if len(step.items) == 1 else None
    return (
        isinstance(only, Op)
        and only.kind in {StitchKind.KNIT, StitchKind.PURL}
        and only.times == step.consumes
    )


def _raglan_marker_body(parts: tuple[bool, ...], lang: str) -> str:
    texts = [t("pattern.raglan_part_inc" if inc else "pattern.raglan_part", lang) for inc in parts]
    if len(set(parts)) == 1:
        return t("pattern.repeat_more", lang, ops=texts[0], n=3)
    if parts[:2] == parts[2:]:
        return t("pattern.repeat_once_more", lang, ops=f"{texts[0]}, {texts[1]}")
    return ", ".join(texts)


def _step_body(step: Step, lang: str, *, markers: bool = False) -> str:
    if markers:
        parts = _raglan_parts(step)
        if parts is not None:
            return _raglan_marker_body(parts, lang)
    paired = _paired_decrease_text(step, lang)
    if paired is not None:
        return paired
    if len(step.items) == 1 and isinstance(step.items[0], Op):
        only = step.items[0]
        if only.times == step.consumes and only.times > 1:
            if only.kind is StitchKind.KNIT:
                return t("pattern.all_knit", lang)
            if only.kind is StitchKind.PURL:
                return t("pattern.all_purl", lang)
    if len(step.items) == 1 and isinstance(step.items[0], Repeat):
        repeat = step.items[0]
        ops = ", ".join(_op_text(op, lang) for op in repeat.ops)
        if _granny_clusters(step):
            return t("pattern.repeat_more", lang, ops=ops, n=repeat.times - 1)
        return t("pattern.repeat_row", lang, ops=ops)
    return ", ".join(_item_text(item, lang) for item in step.items)


def _count_text(step: Step, lang: str) -> str:
    clusters = _granny_clusters(step)
    if clusters:
        return t("pattern.cluster_count", lang, n=clusters)
    return t("pattern.stitch_count_short", lang, n=step.stitch_count_end)


def format_step_line(
    step: Step, mode: str, lang: str, *, relative: bool = False, markers: bool = False
) -> str:
    """Vuelta/hilera explicita, con abreviaturas y conteo declarado.

    `relative`: "Vuelta siguiente" en vez del numero (dos agujas, varios
    talles: el numero de vuelta cambia por talle y no ayuda a seguirlo).
    """
    if relative and step.number > 1:
        label = t("pattern.next_round" if mode == "round" else "pattern.next_row", lang)
    else:
        label = t("pattern.round" if mode == "round" else "pattern.row", lang, n=step.number)
    note = t(step.note_key, lang) + " " if step.note_key else ""
    body = _step_body(step, lang, markers=markers)
    return f"{note}{label}: {body} {_count_text(step, lang)}"


# ---------------------------------------------------------------------------
# Compresion de pasos.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleLine:
    step: Step


@dataclass(frozen=True)
class RangeLine:
    """Vueltas identicas consecutivas: `Vueltas a-b: ...`."""

    first: Step
    last: Step


@dataclass(frozen=True)
class CycleLine:
    """Progresion con ciclo: primer ciclo explicito + `Repetir ...`.

    `explicit` son las lineas del primer ciclo (pueden agrupar vueltas
    identicas internas); `extra_cycles` son las repeticiones que siguen.
    """

    explicit: tuple[StepLine, ...]
    first_number: int
    last_number: int
    extra_cycles: int
    final_step: Step


@dataclass(frozen=True)
class AlternatingLine:
    """Dos hileras que se alternan sin cambiar el conteo (jersey, elastico)."""

    first: Step
    second: Step
    length: int
    last: Step


type StepLine = SingleLine | RangeLine | CycleLine | AlternatingLine


_MIN_ALTERNATING = 4


def _alternating_end(steps: tuple[Step, ...], start: int) -> int:
    """Fin exclusivo de una corrida A, B, A, B... desde `start` (la nota de la
    primera hilera solo la anuncia). Devuelve `start` si no hay corrida."""
    if start + 1 >= len(steps):
        return start
    a, b = steps[start], steps[start + 1]
    count = a.stitch_count_end
    if a.items == b.items or b.note_key or b.stitch_count_end != count or b.consumes != count:
        return start
    if a.consumes != count:
        return start
    end = start + 2
    while end < len(steps):
        step, model = steps[end], steps[end - 2]
        if step.items != model.items or step.note_key or step.stitch_count_end != count:
            break
        end += 1
    return end if end - start >= _MIN_ALTERNATING else start


def _item_shape(item: Item) -> tuple[object, ...]:
    if isinstance(item, Op):
        times: int | None = item.times
        if item.kind in _FILLER_KINDS:
            times = None
        return (item.kind.value, times, item.width)
    # Dentro de una repeticion los conteos se escriben ("*2 mpa, aum*"): no
    # son relleno relativo, asi que no se enmascaran.
    return ("repeat", item.times, tuple((op.kind.value, op.times, op.width) for op in item.ops))


def _step_shape(step: Step) -> tuple[object, ...]:
    return tuple(_item_shape(item) for item in step.items)


def _masked_values(step: Step) -> tuple[int, ...]:
    """Repeticiones de los puntos de relleno, en orden de aparicion."""

    values: list[int] = []

    def collect(item: Item) -> None:
        if isinstance(item, Op):
            if item.kind in _FILLER_KINDS:
                values.append(item.times)
            return

    for item in step.items:
        collect(item)
    return tuple(values)


def _same_step(a: Step, b: Step) -> bool:
    return (
        a.items == b.items
        and a.note_key == b.note_key
        and a.stitch_count_end == b.stitch_count_end
    )


def _is_filler_item(item: Item) -> bool:
    return isinstance(item, Op) and item.kind in _FILLER_KINDS


def _anchor_priority(step: Step) -> int:
    """Prefiere anclar el ciclo en vueltas con nota (aumentos/disminuciones)."""
    if step.note_key:
        return 2
    if any(not _is_filler_item(item) for item in step.items):
        return 1
    return 0


def _identical_lines(
    steps: tuple[Step, ...], start: int, end: int
) -> tuple[StepLine, ...]:
    """Agrupa vueltas identicas consecutivas en el rango [start, end)."""
    lines: list[StepLine] = []
    index = start
    while index < end:
        run_end = index + 1
        while run_end < end and _same_step(steps[index], steps[run_end]):
            run_end += 1
        if run_end - index >= 2:
            lines.append(RangeLine(first=steps[index], last=steps[run_end - 1]))
        else:
            lines.append(SingleLine(step=steps[index]))
        index = run_end
    return tuple(lines)


def _cycle_end(steps: tuple[Step, ...], start: int, cycle: int) -> int:
    """Fin exclusivo de la corrida con ciclo `cycle` que empieza en `start`.

    Requiere que la forma y la nota se repitan con periodo `cycle` y que las
    repeticiones de relleno crezcan con diferencia constante entre ciclos.
    Devuelve `start` si la corrida no alcanza a dos ciclos completos.
    """
    n = len(steps)
    if start + 2 * cycle > n:
        return start
    base_shape = tuple(_step_shape(steps[start + i]) for i in range(cycle))
    base_notes = tuple(steps[start + i].note_key for i in range(cycle))
    deltas: list[tuple[int, ...]] = []
    j = start
    while j < n:
        position = (j - start) % cycle
        step = steps[j]
        if (
            _step_shape(step) != base_shape[position]
            or step.note_key != base_notes[position]
        ):
            break
        vector = _masked_values(step)
        if j - start >= cycle:
            previous = _masked_values(steps[j - cycle])
            if len(vector) != len(previous):
                break
            delta = tuple(b - a for a, b in zip(previous, vector, strict=True))
            if j - start < 2 * cycle:
                deltas.append(delta)
            elif delta != deltas[position]:
                break
        j += 1
    cycles = (j - start) // cycle
    if cycles < 2:
        return start
    return start + cycles * cycle


def _cycle_candidate(
    steps: tuple[Step, ...], start: int, cycle: int
) -> tuple[tuple[StepLine, ...], int, int] | None:
    """Candidato de progresion con ciclo desde `start`.

    Devuelve (lineas, fin exclusivo, ahorro). El ciclo se ancla en la vuelta
    de mayor prioridad dentro del primer ciclo, para que la repeticion empiece
    en un aumento o disminucion como en un patron comercial.
    """
    end = _cycle_end(steps, start, cycle)
    if end == start:
        return None
    anchor = start
    for offset in range(1, cycle):
        shifted = start + offset
        if (end - shifted) // cycle < 2:
            break
        if _anchor_priority(steps[shifted]) > _anchor_priority(steps[anchor]):
            anchor = shifted
    prefix = _identical_lines(steps, start, anchor)
    cycles_available = (end - anchor) // cycle
    leftover_start = anchor + cycles_available * cycle
    leftover = _identical_lines(steps, leftover_start, end)
    explicit = _identical_lines(steps, anchor, anchor + cycle)
    repeat = CycleLine(
        explicit=explicit,
        first_number=steps[anchor].number,
        last_number=steps[anchor + cycle - 1].number,
        extra_cycles=cycles_available - 1,
        final_step=steps[leftover_start - 1],
    )
    lines = (*prefix, repeat, *leftover)
    line_count = len(prefix) + len(explicit) + 1 + len(leftover)
    savings = (end - start) - line_count
    if savings < _MIN_SAVINGS:
        return None
    return lines, end, savings


def _merge_identical(lines: tuple[StepLine, ...]) -> tuple[StepLine, ...]:
    """Fusiona rangos/vueltas identicas que quedaron pegados por las costuras."""
    merged: list[StepLine] = []
    for line in lines:
        if merged and isinstance(line, (SingleLine, RangeLine)):
            previous = merged[-1]
            if isinstance(previous, (SingleLine, RangeLine)):
                previous_step = (
                    previous.step if isinstance(previous, SingleLine) else previous.first
                )
                current_first = (
                    line.step if isinstance(line, SingleLine) else line.first
                )
                if _same_step(previous_step, current_first):
                    current_last = line.last if isinstance(line, RangeLine) else line.step
                    merged[-1] = RangeLine(first=previous_step, last=current_last)
                    continue
        merged.append(line)
    return tuple(merged)


def compress_steps(steps: tuple[Step, ...]) -> tuple[StepLine, ...]:
    """Comprime la secuencia de pasos en lineas presentables.

    Dos compresiones, ambas conservadoras y solo presentacionales:
    - vueltas identicas consecutivas -> una linea de rango;
    - progresiones con ciclo (misma forma, relleno que crece/decrece parejo,
      notas que se repiten) -> primer ciclo explicito + linea de repeticion
      con el conteo final.
    """
    result: list[StepLine] = []
    index = 0
    n = len(steps)
    while index < n:
        alternating = _alternating_end(steps, index)
        if alternating > index:
            result.append(
                AlternatingLine(
                    first=steps[index],
                    second=steps[index + 1],
                    length=alternating - index,
                    last=steps[alternating - 1],
                )
            )
            index = alternating
            continue
        best_lines: tuple[StepLine, ...] | None = None
        best_end = index
        best_savings = 0
        # Rango de vueltas identicas.
        for line in _identical_lines(steps, index, n):
            stretch = 1
            if isinstance(line, RangeLine):
                stretch = line.last.number - line.first.number + 1
            savings = stretch - 1
            if savings > best_savings:
                best_lines = (line,)
                best_end = index + stretch
                best_savings = savings
            break
        # Progresiones con ciclo.
        for cycle in range(1, _MAX_CYCLE + 1):
            candidate = _cycle_candidate(steps, index, cycle)
            if candidate is None:
                continue
            lines, end, savings = candidate
            if savings > best_savings:
                best_lines, best_end, best_savings = lines, end, savings
        if best_lines is not None:
            result.extend(best_lines)
            index = best_end
        else:
            result.append(SingleLine(step=steps[index]))
            index += 1
    return _merge_identical(tuple(result))


def render_step_lines(
    lines: tuple[StepLine, ...],
    mode: str,
    lang: str,
    *,
    relative: bool = False,
    markers: bool = False,
) -> tuple[Block, ...]:
    blocks: list[Block] = []
    rnd = mode == "round"

    def render_alternating(line: AlternatingLine) -> None:
        note = t(line.first.note_key, lang) + " " if line.first.note_key else ""
        count = _count_text(line.last, lang)
        plain = {_is_plain(line.first), _is_plain(line.second)} == {True}
        first_op = line.first.items[0]
        if plain and isinstance(first_op, Op):
            side = "pattern.side_rs" if first_op.kind is StitchKind.KNIT else "pattern.side_ws"
            text = t("pattern.stockinette_rows", lang, n=line.length, side=t(side, lang))
        else:
            text = t(
                "pattern.alternating_rows",
                lang,
                n=line.length,
                a=_step_body(line.first, lang),
                b=_step_body(line.second, lang),
            )
        blocks.append(Block(BlockKind.STEP, f"{note}{text} {count}"))

    def render_one(line: StepLine) -> None:
        if isinstance(line, AlternatingLine):
            render_alternating(line)
            return
        if isinstance(line, SingleLine) and relative and line.step.number > 1 and _is_plain(line.step):
            line = RangeLine(first=line.step, last=line.step)
        if isinstance(line, SingleLine):
            text = format_step_line(line.step, mode, lang, relative=relative, markers=markers)
            blocks.append(Block(BlockKind.STEP, text))
        elif isinstance(line, RangeLine):
            if relative:
                label = t(
                    "pattern.next_rounds" if rnd else "pattern.next_rows",
                    lang,
                    n=line.last.number - line.first.number + 1,
                )
            else:
                label = t(
                    "pattern.rounds_range" if rnd else "pattern.rows_range",
                    lang,
                    a=line.first.number,
                    b=line.last.number,
                )
            note = t(line.first.note_key, lang) + " " if line.first.note_key else ""
            body = _step_body(line.first, lang, markers=markers)
            blocks.append(
                Block(BlockKind.STEP, f"{note}{label}: {body} {_count_text(line.last, lang)}")
            )

    for line in lines:
        if isinstance(line, CycleLine):
            for explicit in line.explicit:
                render_one(explicit)
            length = line.last_number - line.first_number + 1
            if relative:
                key = "pattern.repeat_last_rounds" if rnd else "pattern.repeat_last_rows"
                if length == 1:
                    key = "pattern.repeat_last_round" if rnd else "pattern.repeat_last_row"
                text = t(key, lang, l=length, n=line.extra_cycles, sts=line.final_step.stitch_count_end)
            else:
                text = t(
                    "pattern.rounds_repeat" if rnd else "pattern.rows_repeat",
                    lang,
                    a=line.first_number,
                    b=line.last_number,
                    n=line.extra_cycles,
                    sts=line.final_step.stitch_count_end,
                )
            blocks.append(Block(BlockKind.REPEAT, text))
        else:
            render_one(line)
    return tuple(blocks)


# ---------------------------------------------------------------------------
# Glosario de abreviaturas.
# ---------------------------------------------------------------------------


# Operaciones compuestas: el glosario debe explicar tambien sus partes.
_IMPLIED_KINDS: dict[StitchKind, tuple[StitchKind, ...]] = {
    StitchKind.GRANNY_START: (StitchKind.DC, StitchKind.CH, StitchKind.MAGIC_RING),
    StitchKind.GRANNY_CORNER: (StitchKind.DC, StitchKind.CH, StitchKind.SLST),
    StitchKind.GRANNY_SIDE: (StitchKind.DC, StitchKind.CH),
}


def _used_kinds(pattern: Pattern) -> tuple[StitchKind, ...]:
    seen: list[StitchKind] = []

    def add(kind: StitchKind) -> None:
        for each in (kind, *_IMPLIED_KINDS.get(kind, ())):
            if each not in seen:
                seen.append(each)

    def collect(item: Item) -> None:
        if isinstance(item, Op):
            add(item.kind)
            return
        for op in item.ops:
            add(op.kind)

    for section in pattern.sections:
        for step in section.steps:
            for item in step.items:
                collect(item)
    return tuple(seen)


def glossary_blocks(pattern: Pattern, lang: str) -> tuple[Block, ...]:
    blocks: list[Block] = []
    for kind in _used_kinds(pattern):
        key = f"glossary.{kind.value}"
        if not has_key(key, lang) and not has_key(key, "es"):
            continue
        entry = t(key, lang)
        abbreviation, meaning = entry.split("::", 1)
        blocks.append(
            Block(BlockKind.GLOSSARY, entry, label=abbreviation, value=meaning)
        )
    uses_markers = pattern.meta.family == "raglan_top_down" or any(
        "panel_rows" in section.meta for section in pattern.sections
    )
    if uses_markers:
        for key in ("glossary.marker", "glossary.slip_marker"):
            abbreviation, meaning = t(key, lang).split("::", 1)
            blocks.append(Block(BlockKind.GLOSSARY, t(key, lang), label=abbreviation, value=meaning))
    blocks.sort(key=lambda block: (block.label or "").casefold())
    if blocks:
        sts_entry = t("glossary.sts", lang)
        abbreviation, meaning = sts_entry.split("::", 1)
        blocks.insert(0, Block(BlockKind.GLOSSARY, sts_entry, label=abbreviation, value=meaning))
    return tuple(blocks)


# ---------------------------------------------------------------------------
# Armado del patron completo.
# ---------------------------------------------------------------------------


def _section_intro(section: Section, lang: str) -> str:
    if section.id == "granny_square":
        return t("pattern.granny_ring", lang)
    if section.division:
        parts = ", ".join(t(f"pattern.div.{part}", lang, n=n) for part, n in section.division)
        return t(
            "pattern.separation_round",
            lang,
            parts=parts,
            body=section.meta.get("body", section.end_stitches),
        )
    if section.steps:
        first_ops = section.steps[0].expanded_ops()
        cast_on = sum(op.times for op in first_ops if op.kind is StitchKind.CAST_ON)
        if cast_on:
            return t("pattern.cast_on", lang, n=cast_on)
        if any(op.kind is StitchKind.MAGIC_RING for op in first_ops):
            return t("pattern.magic_ring", lang)
        if any(op.kind is StitchKind.RING for op in first_ops):
            return t("pattern.ring", lang)
        chains = sum(op.times for op in first_ops if op.kind is StitchKind.CH)
        if chains:
            return t("pattern.cast_on_crochet", lang, n=chains)
    if section.id == "neckband":
        return t("pattern.cast_on_round", lang, n=section.start_stitches)
    if section.id == "yoke" and "back_neck" in section.meta:
        meta = section.meta
        return t(
            "pattern.raglan_setup",
            lang,
            back=meta["back_neck"],
            front=meta["front_neck"],
            sleeve=meta["sleeve_neck"],
        )
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


def _half(value: float) -> str:
    """Redondeo a 0,5: los patrones impresos no dan decimas de cm."""
    return f"{round_half_up(value * 2) / 2:g}"


def _length(value_cm: float, units: str, lang: str) -> str:
    if units == "in":
        return f"{_half(value_cm / 2.54)} {t('unit.in', lang)}"
    return f"{_half(value_cm)} {t('unit.cm', lang)}"


def _panel_layout(step: Step, lang: str, width: int) -> str | None:
    """`30 der, mc, 38 pts de panel, mc, 71 der...` desde una vuelta del panel."""
    parts: list[str] = []
    in_panel = False
    for item in step.items:
        plain = isinstance(item, Op) and item.kind in {StitchKind.KNIT, StitchKind.PURL} and item.times > 4
        if plain and isinstance(item, Op):
            if in_panel:
                parts.append(t("pattern.panel_marker", lang))
                in_panel = False
            parts.append(_op_text(item, lang))
        elif not in_panel:
            if parts:
                parts.append(t("pattern.panel_marker", lang))
            parts.append(t("pattern.panel_sts", lang, w=width))
            in_panel = True
    return ", ".join(parts) if parts else None


def _plain_kind(step: Step) -> StitchKind | None:
    """Punto liso de la hilera (der en LD, rev en LR): el Op K/P mas largo."""
    plain = [i for i in step.items if isinstance(i, Op) and i.kind in {StitchKind.KNIT, StitchKind.PURL}]
    return max(plain, key=lambda op: op.times).kind if plain else None


def _panel_spans(step: Step) -> list[tuple[int, int]]:
    """Indices [a, b) de cada panel de la hilera: bordes de 2 pts + repeticion."""
    plain = _plain_kind(step)

    def border(i: int) -> bool:
        item = step.items[i] if 0 <= i < len(step.items) else None
        return (
            isinstance(item, Op)
            and item.times == 2
            and item.kind is not plain
            and item.kind in {StitchKind.KNIT, StitchKind.PURL}
        )

    spans = []
    for index, item in enumerate(step.items):
        if isinstance(item, Repeat):
            start = index - 1 if border(index - 1) else index
            end = index + 2 if border(index + 1) else index + 1
            spans.append((start, end))
    return spans


def _panel_step_body(step: Step, lang: str) -> str:
    """Hilera con panel escrita con marcadores: `1 der, ssk, der hasta el mc,
    panel (grafico 1), der hasta quedar 3 pts, 2pjd, 1 der`."""
    spans = _panel_spans(step)
    if not spans:
        return _step_body(step, lang)
    items = list(step.items)
    tail_edge = len(items) >= 3 and isinstance(items[-2], Op) and items[-2].kind is StitchKind.K2TOG
    parts: list[str] = []
    position = 0
    for number, (a, b) in enumerate([*spans, (len(items), len(items))]):
        segment = items[position:a]
        last_segment = number == len(spans)
        for index, item in enumerate(segment):
            is_plain = isinstance(item, Op) and item.kind in {StitchKind.KNIT, StitchKind.PURL}
            if is_plain and isinstance(item, Op) and (index == len(segment) - 1 or last_segment):
                knit = item.kind is StitchKind.KNIT
                if last_segment and index == 0 and tail_edge:
                    parts.append(t("pattern.paired_decrease_tail", lang))
                    break
                if last_segment:
                    parts.append(t("pattern.plain_to_end_k" if knit else "pattern.plain_to_end_p", lang))
                else:
                    parts.append(t("pattern.plain_to_marker_k" if knit else "pattern.plain_to_marker_p", lang))
            else:
                parts.append(_item_text(item, lang))
        if not last_segment:
            parts.append(t("pattern.panel_inline", lang))
        position = b
    return ", ".join(parts)


def _is_pure_panel_row(step: Step) -> bool:
    spans = _panel_spans(step)
    if not spans or step.stitch_count_end != step.consumes:
        return False
    inside = {i for a, b in spans for i in range(a, b)}
    return all(
        isinstance(item, Op) and item.kind in {StitchKind.KNIT, StitchKind.PURL}
        for index, item in enumerate(step.items)
        if index not in inside
    )


def _panel_section_blocks(section: Section, lang: str, relative: bool) -> tuple[Block, ...] | None:
    """Seccion con panel de textura. Las vueltas de la IR siguen explicitas y
    simuladas; el texto resume los tramos lisos con panel (marcadores +
    grafico) y escribe explicitas las hileras con forma."""
    meta = section.meta
    rows = meta.get("panel_rows")
    start = meta.get("panel_start", 1)
    if not rows or len(section.steps) <= start:
        return None
    first = next((step for step in section.steps[start:] if _is_pure_panel_row(step)), None)
    if first is None:
        return None
    flat = section.mode == "flat"
    width, repeats = meta["panel_width"], meta["panel_repeats"]
    cable = any(
        op.kind in {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}
        for step in section.steps[start : start + rows]
        for item in step.items
        if isinstance(item, Repeat)
        for op in item.ops
    )
    blocks: list[Block] = []
    before = section.steps[1:start] if section.division else section.steps[:start]
    blocks.extend(render_step_lines(compress_steps(before), section.mode, lang, relative=relative))
    blocks.append(Block(BlockKind.LINE, t("pattern.panel_markers", lang, layout=_panel_layout(first, lang, width) or "")))
    blocks.append(
        Block(
            BlockKind.LINE,
            t("pattern.panel_cable" if cable else "pattern.panel_contiguous", lang, w=width, r=repeats),
        )
    )
    steps = section.steps[start:]
    index = 0
    first_run = True
    while index < len(steps):
        end = index
        while end < len(steps) and _is_pure_panel_row(steps[end]):
            end += 1
        if end - index >= 2:
            count = end - index
            run_first = steps[index]
            if flat:
                side = "pattern.side_rs" if _plain_kind(run_first) is StitchKind.KNIT else "pattern.side_ws"
                key = "pattern.panel_rows_flat" if first_run else "pattern.panel_rows_more"
                text = t(key, lang, n=count, rows=rows, side=t(side, lang), sts=steps[end - 1].stitch_count_end)
            else:
                key = "pattern.panel_rounds" if first_run else "pattern.panel_rounds_more"
                text = t(key, lang, n=count, rows=rows, sts=steps[end - 1].stitch_count_end)
            note = t(run_first.note_key, lang) + " " if run_first.note_key else ""
            blocks.append(Block(BlockKind.STEP, note + text))
            first_run = False
            index = end
            continue
        label = t("pattern.next_row" if flat else "pattern.next_round", lang)

        def text_of(step: Step) -> tuple[str | None, str]:
            return step.note_key, _panel_step_body(step, lang)

        # Hileras con forma: si se repiten de a 2 (disminucion + hilera lisa)
        # se escriben una vez y "Repetir las ultimas 2 hileras N veces mas".
        repeats_found = 0
        if index + 3 < len(steps):
            pair = (text_of(steps[index]), text_of(steps[index + 1]))
            j = index + 2
            while j + 1 < len(steps) and (
                (steps[j].note_key is None or steps[j].note_key == pair[0][0])
                and _panel_step_body(steps[j], lang) == pair[0][1]
                and text_of(steps[j + 1]) == pair[1]
            ):
                repeats_found += 1
                j += 2
        for step in steps[index : index + 2] if repeats_found else steps[index : index + 1]:
            note = t(step.note_key, lang) + " " if step.note_key else ""
            blocks.append(
                Block(BlockKind.STEP, f"{note}{label}: {_panel_step_body(step, lang)} {_count_text(step, lang)}")
            )
        if repeats_found:
            last_step = steps[index + 1 + 2 * repeats_found]
            key = "pattern.repeat_last_rows" if flat else "pattern.repeat_last_rounds"
            blocks.append(Block(BlockKind.REPEAT, t(key, lang, l=2, n=repeats_found, sts=last_step.stitch_count_end)))
            index += 2 + 2 * repeats_found
        else:
            index += 1
    first_chart = meta.get("panel_first_chart_row", 1)
    last = (first_chart - 1 + len(steps) - 1) % rows + 1
    blocks.append(Block(BlockKind.LINE, t("pattern.panel_end_flat" if flat else "pattern.panel_end", lang, k=last)))
    return tuple(blocks)


def instruction_blocks(pattern: Pattern, language: str) -> tuple[Block, ...]:
    """Instrucciones por seccion (sin encabezado de documento)."""
    blocks: list[Block] = []
    for section in pattern.sections:
        blocks.append(Block(BlockKind.SECTION_HEADING, t(section.name_key, language)))
        intro = _section_intro(section, language)
        if intro:
            blocks.append(Block(BlockKind.LINE, intro))
        for note_key in section.note_keys:
            blocks.append(Block(BlockKind.LINE, t(note_key, language)))
        steps = section.steps[1:] if section.division else section.steps
        panel = _panel_section_blocks(section, language, pattern.spec.tecnica.value != "crochet")
        if panel is not None:
            blocks.extend(panel)
        else:
            blocks.extend(
                render_step_lines(
                    compress_steps(steps),
                    section.mode,
                    language,
                    relative=pattern.spec.tecnica.value != "crochet",
                    markers=section.id == "yoke" and pattern.meta.family == "raglan_top_down",
                )
            )
        if section.target is not None and section.target.dimension == "length" and section.steps:
            blocks.append(
                Block(
                    BlockKind.LINE,
                    t(
                        "pattern.checkpoint_length",
                        language,
                        length=_length(section.target.target_cm, pattern.params.unidades, language),
                    ),
                )
            )
        if section.bind_off:
            bind_key = (
                "pattern.bind_off_crochet"
                if pattern.spec.tecnica.value == "crochet"
                else "pattern.bind_off"
            )
            if bind_key == "pattern.bind_off_crochet":
                blocks.append(Block(BlockKind.LINE, t(bind_key, language)))
            else:
                blocks.append(
                    Block(BlockKind.LINE, t(bind_key, language, n=section.end_stitches))
                )
    return tuple(blocks)


def build_pattern_blocks(
    pattern: Pattern,
    *,
    lang: str | None = None,
    size_subtitle: bool = True,
) -> tuple[Block, ...]:
    """Convierte la IR verificada en bloques listos para renderizar.

    `size_subtitle=False` para combinar talles: el documento pone su propio
    encabezado con la lista de talles.
    """
    language = lang or pattern.params.idioma
    gauge = resolve_gauge(pattern.params)
    blocks: list[Block] = [Block(BlockKind.TITLE, t(pattern.meta.title_key, language))]
    if size_subtitle and pattern.meta.family in _GARMENT_FAMILIES:
        blocks.append(
            Block(BlockKind.SUBTITLE, t("pattern.size_short", language, size=pattern.meta.size))
        )
    gauge_line = t(
        "pattern.gauge_short",
        language,
        sts=f"{gauge.stitches_per_10cm:g}",
        rows=f"{gauge.rows_per_10cm:g}",
    )
    blocks.append(Block(BlockKind.LINE, gauge_line))

    blocks.append(Block(BlockKind.DOC_HEADING, t("pattern.materials", language)))
    blocks.append(
        Block(
            BlockKind.LINE,
            t(
                "pattern.yarn",
                language,
                weight=t(f"yarn.{pattern.materials.yarn_weight.value}", language),
            ),
        )
    )
    yardage = (
        t("pattern.yardage", language, m=f"{pattern.materials.meters:g}", g=f"{pattern.materials.grams:g}")
        if pattern.materials.grams is not None
        else t("pattern.yardage_no_grams", language, m=f"{pattern.materials.meters:g}")
    )
    blocks.append(Block(BlockKind.LINE, yardage))
    if pattern.materials.needle_mm is not None:
        blocks.append(
            Block(BlockKind.LINE, t("pattern.needles", language, mm=f"{pattern.materials.needle_mm:g}"))
        )
    if pattern.materials.hook_mm is not None:
        blocks.append(
            Block(BlockKind.LINE, t("pattern.hook", language, mm=f"{pattern.materials.hook_mm:g}"))
        )
    if pattern.materials.notions:
        notions = ", ".join(t(key, language) for key in pattern.materials.notions)
        blocks.append(Block(BlockKind.LINE, f"{t('pattern.notions', language)}: {notions}"))
    if pattern.materials.colors:
        blocks.append(
            Block(
                BlockKind.LINE,
                f"{t('color.main', language)}: {', '.join(pattern.materials.colors)}",
            )
        )

    blocks.append(
        Block(BlockKind.DOC_HEADING, t("pattern.finished_measurements", language))
    )
    for measurement in pattern.measurements:
        blocks.append(
            Block(
                BlockKind.MEASURE,
                _length(measurement.value_cm, pattern.params.unidades, language),
                label=t(f"measure.{measurement.key}", language),
            )
        )

    glossary = glossary_blocks(pattern, language)
    if glossary:
        blocks.append(Block(BlockKind.DOC_HEADING, t("pattern.abbreviations", language)))
        blocks.extend(glossary)

    if pattern.warnings:
        blocks.append(Block(BlockKind.DOC_HEADING, t("pattern.notes", language)))
        for warning in pattern.warnings:
            blocks.append(
                Block(
                    BlockKind.WARNING,
                    t(warning.message_key, language, **warning.params),
                )
            )

    blocks.append(Block(BlockKind.DOC_HEADING, t("pattern.instructions", language)))
    blocks.extend(instruction_blocks(pattern, language))

    blocks.append(Block(BlockKind.DOC_HEADING, t("pattern.finished", language)))
    blocks.append(Block(BlockKind.LINE, t("pattern.block", language)))
    blocks.append(Block(BlockKind.LINE, t("pattern.sample_reminder", language)))
    return tuple(blocks)
