"""Combina los bloques de varios talles en un solo patron: `88 (96, 100) p`.

Cada talle se genera y se verifica por separado (el simulador no cambia). Este
modulo es solo presentacion: alinea las lineas de todos los talles por su
"forma" (el texto sin los numeros) y escribe los numeros en el orden de la
tabla de talles. Si un numero es igual en todos los talles se escribe una vez;
si una linea no existe en un talle, ese talle lleva un guion largo y la linea se rotula
"Solo talles ...".

Garantia (testeada): proyectar el texto combinado a cualquier talle devuelve
exactamente el texto de ese talle. Ningun numero se pierde ni se inventa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from engine.blocks import Block, BlockKind
from engine.i18n import t

# Un numero suelto: no parte de una abreviatura como m1l o 2pj.
_NUMBER = re.compile(r"(?<![A-Za-z\d.,])\d+(?:[.,]\d+)?(?![A-Za-z\d])")
_SLOT = "\x00"
NOT_APPLICABLE = "\u2013"  # guion largo, como en los patrones impresos

# Bloques que no se alinean: se unen (sin repetir) en el orden de aparicion.
_UNION_KINDS = {BlockKind.GLOSSARY, BlockKind.WARNING}


def split_numbers(text: str) -> tuple[str, tuple[str, ...]]:
    """Devuelve (forma, numeros): la forma tiene un hueco por cada numero."""
    numbers = tuple(_NUMBER.findall(text))
    return _NUMBER.sub(_SLOT, text), numbers


def format_values(values: tuple[str, ...]) -> str:
    """`88 (96, 100)`; un solo valor si todos coinciden (ignorando el guion)."""
    present = {value for value in values if value != NOT_APPLICABLE}
    if len(present) == 1 and NOT_APPLICABLE not in values:
        return values[0]
    return f"{values[0]} ({', '.join(values[1:])})"


def _fill(shape: str, columns: list[tuple[str, ...]]) -> str:
    parts = shape.split(_SLOT)
    out = [parts[0]]
    for column, tail in zip(columns, parts[1:], strict=True):
        out.append(format_values(column))
        out.append(tail)
    return "".join(out)


@dataclass
class _Row:
    kind: BlockKind
    shapes: tuple[str, str, str]  # text, label, value
    values: list[tuple[tuple[str, ...], ...] | None]  # por talle; None = no aplica

    @property
    def key(self) -> tuple[object, ...]:
        return (self.kind, *self.shapes)


def _row_parts(block: Block) -> tuple[tuple[str, str, str], tuple[tuple[str, ...], ...]]:
    fields = (block.text, block.label or "", block.value or "")
    if block.kind in _UNION_KINDS:
        # Glosario y notas: se alinean por texto completo y no se combinan.
        return fields, ((), (), ())
    split = [split_numbers(field) for field in fields]
    shapes = (split[0][0], split[1][0], split[2][0])
    return shapes, tuple(numbers for _, numbers in split)


def merge_size_blocks(
    per_size: list[tuple[Block, ...]], sizes: list[str], lang: str
) -> tuple[Block, ...]:
    """Alinea los bloques de cada talle y devuelve una sola lista combinada."""
    if len(per_size) != len(sizes) or not sizes:
        raise ValueError("se necesita una lista de bloques por talle")
    if len(sizes) == 1:
        return per_size[0]
    count = len(sizes)
    rows: list[_Row] = []
    for index, blocks in enumerate(per_size):
        parts = [_row_parts(block) for block in blocks]
        keys = [(block.kind, *shapes) for block, (shapes, _) in zip(blocks, parts, strict=True)]
        matcher = SequenceMatcher(a=[row.key for row in rows], b=keys, autojunk=False)
        merged: list[_Row] = []
        for tag, a0, a1, b0, b1 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(a1 - a0):
                    row = rows[a0 + offset]
                    row.values[index] = parts[b0 + offset][1]
                    merged.append(row)
                continue
            merged.extend(rows[a0:a1])
            for offset in range(b1 - b0):
                shapes, numbers = parts[b0 + offset]
                values: list[tuple[tuple[str, ...], ...] | None] = [None] * count
                values[index] = numbers
                merged.append(_Row(blocks[b0 + offset].kind, shapes, values))
        rows = merged
    return tuple(_render_row(row, sizes, lang) for row in rows)


def _render_row(row: _Row, sizes: list[str], lang: str) -> Block:
    present = [i for i, values in enumerate(row.values) if values is not None]
    partial = len(present) < len(sizes) and row.kind in _PARTIAL_KINDS
    # Linea de algunos talles: "Solo talles L, XL: ... 7 (14) ...", con los
    # valores solo de esos talles (convencion de los patrones impresos).
    columns_of = present if partial else list(range(len(sizes)))
    fields: list[str] = []
    for field_index, shape in enumerate(row.shapes):
        columns = []
        for slot in range(shape.count(_SLOT)):
            column = []
            for i in columns_of:
                values = row.values[i]
                column.append(values[field_index][slot] if values is not None else NOT_APPLICABLE)
            columns.append(tuple(column))
        fields.append(_fill(shape, columns))
    text, label, value = fields
    if partial:
        only = ", ".join(sizes[i] for i in present)
        text = f"{t('pattern.only_sizes', lang, sizes=only)} {text}"
    return Block(row.kind, text, label=label or None, value=value or None)


_PARTIAL_KINDS = {BlockKind.STEP, BlockKind.REPEAT, BlockKind.LINE}


def project_to_size(text: str, index: int) -> str:
    """Inversa de la notacion: el texto que corresponde al talle `index`."""

    def pick(match: re.Match[str]) -> str:
        first, rest = match.group(1), match.group(2)
        values = [first, *[value.strip() for value in rest.split(",")]]
        return values[index]

    return _MULTI.sub(pick, text)


_VALUE = rf"(?:\d+(?:[.,]\d+)?|{NOT_APPLICABLE})"
_MULTI = re.compile(rf"({_VALUE}) \(({_VALUE}(?:, {_VALUE})*)\)")


def size_note(sizes: list[str], lang: str) -> str:
    return t(
        "pattern.size_note",
        lang,
        first=sizes[0],
        rest=", ".join(sizes[1:]),
    )


__all__ = [
    "NOT_APPLICABLE",
    "format_values",
    "merge_size_blocks",
    "project_to_size",
    "size_note",
    "split_numbers",
]
