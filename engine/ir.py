"""Representacion intermedia (IR) de un patron.

La IR es la salida estructurada final del motor: de aca se generan el texto,
los graficos, el PDF y la vista web. El simulador consume esta misma IR,
nunca los calculos internos del generador.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from engine.spec import GarmentSpec, PatternParams, YarnWeight
from engine.stitches.kinds import StitchKind, stitch_effect

_CABLES = {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}


@dataclass(frozen=True)
class Op:
    """Una instruccion atomica repetida `times` veces.

    Ejemplos: `Op(KNIT, times=8)` = "8 derechos";
    `Op(K2TOG, times=3)` = "3 veces 2 puntos juntos";
    `Op(CABLE_FRONT, width=4)` = "cable de 4 puntos cruzado al frente".
    """

    kind: StitchKind
    times: int = 1
    width: int | None = None

    def __post_init__(self) -> None:
        if self.times < 1:
            raise ValueError(f"times debe ser >= 1, no {self.times}")
        if (self.kind in _CABLES or self.kind is StitchKind.RING) and self.width is None:
            raise ValueError(f"{self.kind.value} requiere width")
        stitch_effect(self.kind, self.width)

    @property
    def consumes(self) -> int:
        return stitch_effect(self.kind, self.width).consumes * self.times

    @property
    def produces(self) -> int:
        return stitch_effect(self.kind, self.width).produces * self.times


@dataclass(frozen=True)
class Repeat:
    """Un grupo de instrucciones repetido `times` veces."""

    times: int
    ops: tuple[Op, ...]

    def __post_init__(self) -> None:
        if self.times < 1:
            raise ValueError(f"times debe ser >= 1, no {self.times}")
        if not self.ops:
            raise ValueError("un Repeat necesita al menos un Op")

    @property
    def consumes(self) -> int:
        return self.times * sum(op.consumes for op in self.ops)

    @property
    def produces(self) -> int:
        return self.times * sum(op.produces for op in self.ops)


type Item = Op | Repeat


@dataclass(frozen=True)
class Step:
    """Una vuelta o hilera. `stitch_count_end` es el conteo declarado."""

    number: int
    items: tuple[Item, ...]
    stitch_count_end: int
    note_key: str | None = None
    # Parametros del texto de la nota (por ejemplo, el color de una banda).
    note_params: tuple[tuple[str, str], ...] = ()

    @property
    def note(self) -> tuple[str | None, tuple[tuple[str, str], ...]]:
        return self.note_key, self.note_params

    def __post_init__(self) -> None:
        if self.number < 0:
            raise ValueError("el numero de vuelta no puede ser negativo")
        if self.stitch_count_end < 0:
            raise ValueError("el conteo final no puede ser negativo")

    @property
    def consumes(self) -> int:
        return sum(item.consumes for item in self.items)

    @property
    def produces(self) -> int:
        return sum(item.produces for item in self.items)

    def expanded_ops(self) -> tuple[Op, ...]:
        """Expande repeticiones y `times`: un Op por punto atomico.

        Los cables conservan su `width` (son una unidad, no puntos sueltos).
        """
        result: list[Op] = []
        for item in self.items:
            ops = (item,) if isinstance(item, Op) else item.ops
            repeats = 1 if isinstance(item, Op) else item.times
            for _ in range(repeats):
                for op in ops:
                    if op.times == 1:
                        result.append(op)
                    else:
                        single = Op(op.kind, times=1, width=op.width)
                        result.extend([single] * op.times)
        return tuple(result)


def division_ops(division: Sequence[tuple[str, int]]) -> tuple[Op, ...]:
    """Ops de una vuelta de separacion. "hold" no se teje en esta seccion."""
    kinds = {"knit": StitchKind.KNIT, "cast_on": StitchKind.CAST_ON}
    return tuple(Op(kinds[part], times=n) for part, n in division if part != "hold" and n)


def build_step(
    number: int,
    start_stitches: int,
    items: Sequence[Item],
    note_key: str | None = None,
    note_params: tuple[tuple[str, str], ...] = (),
) -> Step:
    """Construye un paso que consume exactamente los puntos disponibles.

    Es el constructor recomendado para los generadores: si un paso no consume
    todos los puntos (o consume de mas), falla aca y no llega al simulador.
    """
    step = Step(
        number=number, items=tuple(items), stitch_count_end=0, note_key=note_key, note_params=note_params
    )
    if step.consumes != start_stitches:
        raise ValueError(
            f"vuelta {number}: consume {step.consumes} puntos, hay {start_stitches}"
        )
    end = start_stitches - step.consumes + step.produces
    return replace(step, stitch_count_end=end)


@dataclass(frozen=True)
class SectionTarget:
    """Medida objetivo de una seccion, verificada por el simulador."""

    measurement_key: str
    target_cm: float
    tolerance_cm: float = 1.0
    dimension: Literal["circumference", "width", "length"] = "circumference"


@dataclass(frozen=True)
class CountRef:
    """Referencia a un conteo de una seccion.

    `field` puede ser "start", "end" o "meta:<clave>" para valores extra
    declarados por el generador (por ejemplo, puntos levantados en la axila).
    """

    section: str
    field: str


@dataclass(frozen=True)
class JoinCheck:
    """Comprobacion de union: suma de un lado == suma del otro."""

    label_key: str
    left: tuple[CountRef, ...]
    right: tuple[CountRef, ...]


@dataclass(frozen=True)
class Section:
    id: str
    name_key: str
    mode: Literal["flat", "round"]
    steps: tuple[Step, ...]
    start_stitches: int
    end_stitches: int
    target: SectionTarget | None = None
    meta: dict[str, int] = field(default_factory=dict)
    bind_off: bool = False
    note_keys: tuple[str, ...] = ()
    # Vuelta de separacion en orden fisico: ("knit"|"hold"|"cast_on", n).
    division: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if self.start_stitches < 0 or self.end_stitches < 0:
            raise ValueError("los conteos de seccion no pueden ser negativos")

    def count_for(self, field_name: str) -> int:
        if field_name == "start":
            return self.start_stitches
        if field_name == "end":
            return self.end_stitches
        if field_name.startswith("meta:"):
            key = field_name.removeprefix("meta:")
            if key not in self.meta:
                raise KeyError(f"la seccion {self.id!r} no declara meta:{key}")
            return self.meta[key]
        raise ValueError(f"campo de conteo desconocido: {field_name!r}")


@dataclass(frozen=True)
class Measurement:
    key: str
    value_cm: float
    target_cm: float | None = None
    tolerance_cm: float = 0.0
    kind: Literal["circumference", "width", "length"] = "circumference"


@dataclass(frozen=True)
class Materials:
    yarn_weight: YarnWeight
    needle_mm: float | None
    hook_mm: float | None
    meters: float
    grams: float | None = None
    notions: tuple[str, ...] = ()
    colors: tuple[str, ...] = ()
    # Metros por color, en el orden de `colors` (vacio si no se estima).
    color_meters: tuple[float, ...] = ()


@dataclass(frozen=True)
class Warning:
    code: str
    message_key: str
    params: dict[str, str | int | float] = field(default_factory=dict)
    severity: Literal["info", "warning", "error"] = "warning"


@dataclass(frozen=True)
class PatternMeta:
    id: str
    family: str
    title_key: str
    size: str
    created_at: str
    engine_version: str


@dataclass(frozen=True)
class Pattern:
    meta: PatternMeta
    spec: GarmentSpec
    params: PatternParams
    sections: tuple[Section, ...]
    measurements: tuple[Measurement, ...]
    materials: Materials
    warnings: tuple[Warning, ...] = ()
    joins: tuple[JoinCheck, ...] = ()
    notes: tuple[str, ...] = ()

    def section(self, section_id: str) -> Section:
        for section in self.sections:
            if section.id == section_id:
                return section
        raise KeyError(f"seccion desconocida: {section_id!r}")

    @property
    def total_steps(self) -> int:
        return sum(len(section.steps) for section in self.sections)
