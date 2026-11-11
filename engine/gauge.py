"""Densidad (gauge): puntos y vueltas por 10 cm."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from engine.rounding import round_half_up


class Gauge(BaseModel):
    """Densidad de la muestra. Inmutable y validada."""

    model_config = ConfigDict(frozen=True)

    stitches_per_10cm: float = Field(gt=0, le=100)
    rows_per_10cm: float = Field(gt=0, le=100)

    @property
    def stitches_per_cm(self) -> float:
        return self.stitches_per_10cm / 10.0

    @property
    def rows_per_cm(self) -> float:
        return self.rows_per_10cm / 10.0

    def stitches_for_cm(self, cm: float) -> int:
        """Puntos necesarios para un ancho, redondeado half-up."""
        if cm < 0:
            raise ValueError("el ancho no puede ser negativo")
        return round_half_up(cm * self.stitches_per_cm)

    def rows_for_cm(self, cm: float) -> int:
        """Vueltas necesarias para un largo, redondeado half-up."""
        if cm < 0:
            raise ValueError("el largo no puede ser negativo")
        return round_half_up(cm * self.rows_per_cm)

    def cm_for_stitches(self, stitches: int) -> float:
        if stitches < 0:
            raise ValueError("los puntos no pueden ser negativos")
        return stitches / self.stitches_per_cm

    def cm_for_rows(self, rows: int) -> float:
        if rows < 0:
            raise ValueError("las vueltas no pueden ser negativas")
        return rows / self.rows_per_cm


# Densidades de referencia por grosor de hilo (puntos y vueltas por 10 cm).
# Fuente: Craft Yarn Council, Standard Yarn Weight System (rangos de muestra).
# Se usa el punto medio de cada rango; es una referencia editable, no una
# medicion de la prenda real. Ver docs/fuentes.md.
DEFAULT_GAUGES: dict[str, Gauge] = {
    "lace": Gauge(stitches_per_10cm=36.0, rows_per_10cm=48.0),
    "fingering": Gauge(stitches_per_10cm=30.0, rows_per_10cm=40.0),
    "sport": Gauge(stitches_per_10cm=24.0, rows_per_10cm=32.0),
    "dk": Gauge(stitches_per_10cm=22.0, rows_per_10cm=30.0),
    "worsted": Gauge(stitches_per_10cm=18.0, rows_per_10cm=24.0),
    "bulky": Gauge(stitches_per_10cm=14.0, rows_per_10cm=18.0),
    "super_bulky": Gauge(stitches_per_10cm=9.0, rows_per_10cm=12.0),
}


# Crochet: puntos bajos por 10 cm (4 in) segun Craft Yarn Council, Standard
# Yarn Weight System, punto medio del rango "crochet gauge ranges in single
# crochet to 4 inch" (verificado en craftyarncouncil.com el 2026-11-11):
# 1 super fine 21-32, 2 fine 16-20, 3 light 12-17, 4 medium 11-14,
# 5 bulky 8-11, 6 super bulky 7-9. Lace (0) se publica en punto alto (32-42);
# ASUNCION: 32 pb.
CROCHET_SC_PER_10CM: dict[str, float] = {
    "lace": 32.0,
    "fingering": 26.5,
    "sport": 18.0,
    "dk": 14.5,
    "worsted": 12.5,
    "bulky": 9.5,
    "super_bulky": 8.0,
}

# ASUNCION (CYC no publica vueltas): ancho y alto relativos al punto bajo.
# Un pb es casi cuadrado; el pma ~1,5 veces mas alto y el pa ~2 veces.
# Valores habituales de muestras publicadas, no una tabla oficial.
_CROCHET_SHAPE: dict[str, tuple[float, float]] = {
    "crochet_sc": (1.0, 1.1),
    "crochet_hdc": (0.95, 0.75),
    "crochet_dc": (0.9, 0.55),
}


def crochet_gauge(weight: str, stitch_id: str) -> Gauge:
    """Densidad de referencia de crochet para un grosor y un punto base."""
    sc = CROCHET_SC_PER_10CM.get(weight, CROCHET_SC_PER_10CM["dk"])
    width, height = _CROCHET_SHAPE.get(stitch_id, _CROCHET_SHAPE["crochet_sc"])
    return Gauge(
        stitches_per_10cm=round(sc * width, 1), rows_per_10cm=round(sc * height, 1)
    )
