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
