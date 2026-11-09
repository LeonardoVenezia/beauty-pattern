"""Especificacion de la prenda (salida validada de la IA) y parametros de usuario.

Todos los campos usan listas cerradas de valores (enums). Un valor fuera de
la lista es rechazado por Pydantic: nunca se inventa una categoria.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engine.gauge import DEFAULT_GAUGES, Gauge


class Category(StrEnum):
    PULLOVER = "pullover"
    CARDIGAN = "cardigan"
    VEST = "vest"
    HAT = "hat"
    SCARF = "scarf"
    COWL = "cowl"
    MITTENS = "mittens"
    GLOVES = "gloves"
    SOCKS = "socks"
    SHAWL = "shawl"
    BLANKET = "blanket"
    BAG = "bag"
    AMIGURUMI = "amigurumi"
    OTHER = "other"


class Technique(StrEnum):
    NEEDLES = "needles"
    CIRCULAR = "circular"
    CROCHET = "crochet"
    MACHINE = "machine"


class Construction(StrEnum):
    RAGLAN_TOP_DOWN = "raglan_top_down"
    DROP_SHOULDER = "drop_shoulder"
    SET_IN_SLEEVE = "set_in_sleeve"
    YOKE = "yoke"
    BOTTOM_UP = "bottom_up"
    IN_ONE_PIECE = "in_one_piece"
    FLAT_PANELS = "flat_panels"
    ROUND_TUBE = "round_tube"
    MODULES = "modules"
    OTHER = "other"


class Neckline(StrEnum):
    CREW = "crew"
    V_NECK = "v_neck"
    BOAT = "boat"
    TURTLENECK = "turtleneck"
    FUNNEL = "funnel"
    HOOD = "hood"
    SQUARE = "square"
    NONE = "none"


class BodyLength(StrEnum):
    CROPPED = "cropped"
    HIP = "hip"
    TUNIC = "tunic"
    LONG = "long"


class SleeveLength(StrEnum):
    SLEEVELESS = "sleeveless"
    SHORT = "short"
    THREE_QUARTER = "three_quarter"
    LONG = "long"


class Fit(StrEnum):
    VERY_LOOSE = "very_loose"
    LOOSE = "loose"
    REGULAR = "regular"
    FITTED = "fitted"


class Shape(StrEnum):
    STRAIGHT = "straight"
    A_LINE = "a_line"
    BOXY = "boxy"
    CURVED = "curved"


class StitchPatternName(StrEnum):
    STOCKINETTE = "stockinette"
    GARTER = "garter"
    SEED = "seed"
    RIB_1X1 = "rib_1x1"
    RIB_2X2 = "rib_2x2"
    RIB_3X1 = "rib_3x1"
    MOSS = "moss"
    BRIOCHE = "brioche"
    CABLES = "cables"
    LACE = "lace"
    BOBBLES = "bobbles"
    HONEYCOMB = "honeycomb"
    CROCHET_SC = "crochet_sc"
    CROCHET_HDC = "crochet_hdc"
    CROCHET_DC = "crochet_dc"
    OTHER = "other"


class Texture(StrEnum):
    CABLES = "cables"
    LACE = "lace"
    BOBBLES = "bobbles"
    HONEYCOMB = "honeycomb"
    RIBBING = "ribbing"
    CABLED_RIBBING = "cabled_ribbing"
    OTHER = "other"


class ColorworkType(StrEnum):
    NONE = "none"
    STRIPES = "stripes"
    FAIR_ISLE = "fair_isle"
    INTARSIA = "intarsia"
    MOSAIC = "mosaic"


class Finish(StrEnum):
    CUFFS = "cuffs"
    HEM_BAND = "hem_band"
    NECKBAND = "neckband"
    BUTTON_BAND = "button_band"
    POCKETS = "pockets"
    FRINGE = "fringe"
    HOOD = "hood"
    LINING = "lining"


class YarnWeight(StrEnum):
    LACE = "lace"
    FINGERING = "fingering"
    SPORT = "sport"
    DK = "dk"
    WORSTED = "worsted"
    BULKY = "bulky"
    SUPER_BULKY = "super_bulky"
    UNKNOWN = "unknown"


class YarnLook(StrEnum):
    SMOOTH = "smooth"
    MOHAIR = "mohair"
    BOUCLE = "boucle"
    MARLED = "marled"
    CHENILLE = "chenille"
    UNKNOWN = "unknown"


class TextureObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    textura: Texture
    ubicacion: str | None = None
    repeticion_estimada: str | None = None


class Colorwork(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: ColorworkType
    zona: str | None = None
    colores: int = Field(default=2, ge=1, le=8)
    paleta: list[str] = Field(default_factory=list)


class YarnAppearance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grosor_estimado: YarnWeight | None = None
    aspecto: YarnLook | None = None


class GarmentSpec(BaseModel):
    """Lo que la foto permite afirmar. Nunca contiene medidas ni conteos."""

    model_config = ConfigDict(extra="forbid")

    categoria: Category
    tecnica: Technique = Technique.NEEDLES
    construccion: Construction | None = None
    escote: Neckline | None = None
    largo_cuerpo: BodyLength | None = None
    largo_manga: SleeveLength | None = None
    ajuste: Fit | None = None
    forma: Shape | None = None
    punto_base: StitchPatternName | None = None
    texturas: list[TextureObservation] = Field(default_factory=list)
    colorwork: Colorwork | None = None
    acabados: list[Finish] = Field(default_factory=list)
    hilo_aparente: YarnAppearance | None = None
    incertidumbres: list[str] = Field(default_factory=list)
    no_visible: list[str] = Field(default_factory=list)
    confianza: dict[str, float] = Field(default_factory=dict)
    observaciones: str = ""

    @field_validator("confianza")
    @classmethod
    def _confianza_en_rango(cls, value: dict[str, float]) -> dict[str, float]:
        for key, number in value.items():
            if not 0.0 <= number <= 1.0:
                raise ValueError(f"confianza fuera de [0,1] para {key!r}: {number}")
        return value


class PatternParams(BaseModel):
    """Parametros que elige la persona: talle, densidad, idioma, etc."""

    model_config = ConfigDict(extra="forbid")

    talla: str = "M"
    medidas_cm: dict[str, float] = Field(default_factory=dict)
    densidad: Gauge | None = None
    ease_cm: float | None = Field(default=None, ge=-10, le=40)
    idioma: Literal["es", "en"] = "es"
    nivel: Literal["principiante", "experta"] = "principiante"
    unidades: Literal["cm", "in"] = "cm"
    peso_hilo: YarnWeight = YarnWeight.DK
    aguja_mm: float | None = Field(default=None, gt=0, le=25)
    ganchillo_mm: float | None = Field(default=None, gt=0, le=25)
    tecnica: Technique | None = None

    @field_validator("medidas_cm")
    @classmethod
    def _medidas_positivas(cls, value: dict[str, float]) -> dict[str, float]:
        for key, number in value.items():
            if number <= 0:
                raise ValueError(f"medida invalida para {key!r}: {number}")
        return value


def resolve_gauge(params: PatternParams) -> Gauge:
    """Densidad efectiva: la del usuario o la referencia por grosor de hilo."""
    if params.densidad is not None:
        return params.densidad
    return DEFAULT_GAUGES.get(params.peso_hilo.value, DEFAULT_GAUGES["dk"])
