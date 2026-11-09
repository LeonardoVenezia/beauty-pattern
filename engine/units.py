"""Unidades y formato.

Internamente TODO se calcula en centimetros. Las pulgadas son solo una
unidad de presentacion.
"""

from __future__ import annotations

from fractions import Fraction

CM_PER_INCH = 2.54


def inches_to_cm(value_in: float) -> float:
    return value_in * CM_PER_INCH


def cm_to_inches(value_cm: float) -> float:
    return value_cm / CM_PER_INCH


def format_cm(value_cm: float) -> str:
    """Formatea cm con un decimal como maximo, sin .0 innecesario."""
    rounded = round(value_cm, 1)
    if rounded == int(rounded):
        return f"{int(rounded)} cm"
    return f"{rounded:.1f} cm"


def format_inches(value_cm: float) -> str:
    """Formatea pulgadas al cuarto de pulgada mas cercano."""
    quarters = round(cm_to_inches(value_cm) * 4)
    whole, rest = divmod(quarters, 4)
    if rest == 0:
        return f'{whole}"'
    fraction = Fraction(rest, 4)
    return f'{whole} {fraction.numerator}/{fraction.denominator}"'


def format_length(value_cm: float, units: str) -> str:
    if units == "in":
        return format_inches(value_cm)
    return format_cm(value_cm)
