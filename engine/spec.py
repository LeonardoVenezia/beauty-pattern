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
    GRANNY_SQUARE = "granny_square"
    BAG = "bag"
    AMIGURUMI = "amigurumi"
    # Ampliacion D037 (investigacion 2026-11): prendas, accesorios y hogar.
    TOP = "top"  # musculosa, remera, crop
    COAT = "coat"  # saco, tapado, campera
    DRESS = "dress"  # vestido o tunica
    PONCHO = "poncho"  # poncho, ruana, capa
    SHRUG = "shrug"  # bolero
    FINGERLESS_MITTS = "fingerless_mitts"
    BALACLAVA = "balaclava"
    HEADBAND = "headband"  # vincha, cubreorejas
    LEG_WARMERS = "leg_warmers"
    BOOTIES = "booties"  # escarpines
    SLIPPERS = "slippers"
    FLAT_ITEM = "flat_item"  # posavasos, individual, agarradera, pano, carpeta
    COZY = "cozy"  # funda: mate, termo, taza, botella, celular, anteojos, cartuchera
    BASKET = "basket"
    PILLOW = "pillow"
    RUG = "rug"
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
    MODIFIED_DROP_SHOULDER = "modified_drop_shoulder"
    SADDLE_SHOULDER = "saddle_shoulder"
    DOLMAN = "dolman"  # manga murcielago
    T_SHAPE = "t_shape"  # rectangulos (tipico de crochet)
    SIDE_TO_SIDE = "side_to_side"
    OTHER = "other"


class Neckline(StrEnum):
    CREW = "crew"
    V_NECK = "v_neck"
    BOAT = "boat"
    TURTLENECK = "turtleneck"
    FUNNEL = "funnel"
    HOOD = "hood"
    SQUARE = "square"
    MOCK_NECK = "mock_neck"  # cuello alto corto
    SCOOP = "scoop"
    HENLEY = "henley"  # tapa con botones o medio cierre
    POLO = "polo"
    SHAWL_COLLAR = "shawl_collar"
    COWL_NECK = "cowl_neck"
    NONE = "none"


class BodyLength(StrEnum):
    CROPPED = "cropped"
    WAIST = "waist"
    HIP = "hip"
    TUNIC = "tunic"
    LONG = "long"


class SleeveLength(StrEnum):
    SLEEVELESS = "sleeveless"
    SHORT = "short"
    ELBOW = "elbow"
    THREE_QUARTER = "three_quarter"
    LONG = "long"


class Fit(StrEnum):
    VERY_LOOSE = "very_loose"
    OVERSIZED = "oversized"
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
    REVERSE_STOCKINETTE = "reverse_stockinette"
    TWISTED_RIB = "twisted_rib"
    BROKEN_RIB = "broken_rib"
    BASKETWEAVE = "basketweave"
    WAFFLE = "waffle"
    LINEN = "linen"  # punto lino (puntos deslizados)
    CROCHET_TR = "crochet_tr"
    CROCHET_RIBBING = "crochet_ribbing"  # por la hebra de atras
    GRANNY_STITCH = "granny_stitch"
    CROCHET_LINEN = "crochet_linen"  # punto musgo/lino de crochet
    V_STITCH = "v_stitch"
    SHELL = "shell"  # abanico
    FILET = "filet"  # red
    TUNISIAN = "tunisian"
    C2C = "c2c"
    OTHER = "other"


class Texture(StrEnum):
    CABLES = "cables"
    LACE = "lace"
    BOBBLES = "bobbles"
    HONEYCOMB = "honeycomb"
    RIBBING = "ribbing"
    CABLED_RIBBING = "cabled_ribbing"
    ARAN = "aran"  # trenzas en toda la pieza
    TWISTED_STITCHES = "twisted_stitches"
    RUFFLES = "ruffles"
    MESH = "mesh"
    OTHER = "other"


class ColorworkType(StrEnum):
    NONE = "none"
    STRIPES = "stripes"
    FAIR_ISLE = "fair_isle"
    INTARSIA = "intarsia"
    MOSAIC = "mosaic"
    COLOR_BLOCK = "color_block"
    TAPESTRY = "tapestry"  # tapestry crochet


class Finish(StrEnum):
    CUFFS = "cuffs"
    HEM_BAND = "hem_band"
    NECKBAND = "neckband"
    BUTTON_BAND = "button_band"
    POCKETS = "pockets"
    FRINGE = "fringe"
    HOOD = "hood"
    LINING = "lining"
    POMPOM = "pompom"
    ZIPPER = "zipper"
    COLLAR = "collar"
    TIES = "ties"  # lazos, cordon
    EARFLAPS = "earflaps"
    EDGING = "edging"  # picot, abanico, cangrejo, i-cord
    RUFFLE = "ruffle"


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
    TWEED = "tweed"
    VARIEGATED = "variegated"  # jaspeado, tenido a mano
    SELF_STRIPING = "self_striping"
    COTTON_MATTE = "cotton_matte"
    CHUNKY = "chunky"  # XXL
    RAFFIA = "raffia"
    TAPE = "tape"  # trapillo, cinta
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


class ToyBody(StrEnum):
    """Forma del juguete: en piezas (cabeza y cuerpo aparte, sentado) o
    bolita (cabeza y cuerpo son una sola pieza redonda, sin cuello)."""

    PIECES = "pieces"
    BALL = "ball"
    SEAMLESS = "seamless"  # cabeza y cuerpo de una pieza, con cuello
    STANDING = "standing"  # de pie (munecas, cuadrupedos)
    LONG = "long"  # alargado: serpiente, salchicha
    RADIAL = "radial"  # pulpo, medusa


class Figure(StrEnum):
    """Plantilla de juguete (amigurumi). La IA solo elige la categoria; las
    proporciones de cada pieza salen de engine/garments/toy.py."""

    BEAR = "bear"
    BUNNY = "bunny"
    CAT = "cat"
    DOG = "dog"
    ELEPHANT = "elephant"
    OCTOPUS = "octopus"
    DINOSAUR = "dinosaur"
    UNICORN = "unicorn"
    WHALE = "whale"
    TURTLE = "turtle"
    DUCK = "duck"
    FROG = "frog"
    BEE = "bee"
    COW = "cow"
    SHEEP = "sheep"
    MOUSE = "mouse"
    FOX = "fox"
    OWL = "owl"
    PENGUIN = "penguin"
    PIG = "pig"
    LION = "lion"
    DOLL = "doll"
    GENERIC = "generic"  # muneco sin orejas (cuerpo de osito o de muneca)


class MotifShape(StrEnum):
    CIRCLE = "circle"
    SQUARE = "square"
    HEXAGON = "hexagon"


class GrannyStyle(StrEnum):
    CLASSIC = "classic"  # grupos de 3 pa
    SOLID = "solid"  # macizo
    FLOWER = "flower"  # flor al centro / sunburst


class HatStyle(StrEnum):
    BEANIE = "beanie"
    SLOUCHY = "slouchy"
    BUCKET = "bucket"  # piluso
    BERET = "beret"  # boina
    EARFLAP = "earflap"  # chullo
    BRIMMED = "brimmed"  # capelina, casquete de red
    BONNET = "bonnet"  # capota


class FlatItem(StrEnum):
    COASTER = "coaster"
    PLACEMAT = "placemat"
    POTHOLDER = "potholder"
    DISHCLOTH = "dishcloth"
    DOILY = "doily"


class FlatShape(StrEnum):
    CIRCLE = "circle"
    SQUARE = "square"
    RECTANGLE = "rectangle"
    OVAL = "oval"


class CozyItem(StrEnum):
    MATE = "mate"
    THERMOS = "thermos"
    CUP = "cup"
    BOTTLE = "bottle"
    PHONE = "phone"
    GLASSES = "glasses"
    PENCIL_CASE = "pencil_case"
    LAPTOP = "laptop"


class SleeveStyle(StrEnum):
    STRAIGHT = "straight"
    PUFF = "puff"  # globo, obispo
    BELL = "bell"  # campana
    CAP = "cap"  # casquillo


class PonchoStyle(StrEnum):
    CLASSIC = "classic"  # dos rectangulos cosidos, punta adelante (en V)
    RUANA = "ruana"  # un rectangulo abierto adelante (ruana, capa abierta)


class BlanketStyle(StrEnum):
    GRANNY_JOINED = "granny_joined"
    GRANNY_GIANT = "granny_giant"
    ROWS = "rows"  # rayas o un solo punto
    C2C = "c2c"
    RIPPLE = "ripple"
    HEXAGONS = "hexagons"
    MITERED = "mitered"


class MotifStitch(StrEnum):
    SC = "sc"
    HDC = "hdc"
    DC = "dc"
    TR = "tr"
    MESH = "mesh"  # red: pa separados por cadenas
    CLUSTER = "cluster"
    POPCORN = "popcorn"
    PUFF = "puff"


class MotifBand(BaseModel):
    """Una banda del motivo, del centro hacia afuera."""

    model_config = ConfigDict(extra="forbid")

    punto: MotifStitch
    color: int | None = Field(default=None, ge=0, le=7)  # indice en la paleta
    peso: int = Field(default=1, ge=1, le=4)  # grosor relativo de la banda


class MotifDesign(BaseModel):
    """Estructura de un motivo radial de crochet (mandala, carpeta, cuadrado).

    Es una descripcion de lo que se ve, con vocabulario cerrado. Los conteos
    de puntos y la cantidad de vueltas los calcula el motor para la medida
    pedida (engine/garments/motif.py).
    """

    model_config = ConfigDict(extra="forbid")

    forma: MotifShape = MotifShape.CIRCLE
    simetria: int = Field(default=8, ge=3, le=24)  # petalos o repeticiones radiales
    bandas: list[MotifBand] = Field(min_length=1, max_length=16)
    cuadrar_en_banda: int | None = Field(default=None, ge=0, le=15)
    estilo_granny: GrannyStyle | None = None


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
    motivo: MotifDesign | None = None
    figura: Figure | None = None  # solo amigurumi
    cuerpo_juguete: ToyBody | None = None  # solo amigurumi
    estilo_manga: SleeveStyle | None = None
    estilo_gorro: HatStyle | None = None  # solo hat
    objeto_plano: FlatItem | None = None  # solo flat_item
    forma_plana: FlatShape | None = None  # flat_item, rug, pillow, basket
    objeto_funda: CozyItem | None = None  # solo cozy
    estilo_manta: BlanketStyle | None = None  # solo blanket
    estilo_poncho: PonchoStyle | None = None  # solo poncho
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


Language = Literal["es", "en", "fr", "de", "it"]
LANGUAGES: tuple[Language, ...] = ("es", "en", "fr", "de", "it")


class PatternParams(BaseModel):
    """Parametros que elige la persona: talle, densidad, idioma, etc."""

    model_config = ConfigDict(extra="forbid")

    talla: str = "M"
    medidas_cm: dict[str, float] = Field(default_factory=dict)
    dimensiones_cm: dict[str, float] = Field(default_factory=dict)
    densidad: Gauge | None = None
    ease_cm: float | None = Field(default=None, ge=-10, le=40)
    idioma: Language = "es"
    nivel: Literal["principiante", "experta"] = "principiante"
    unidades: Literal["cm", "in"] = "cm"
    peso_hilo: YarnWeight = YarnWeight.DK
    aguja_mm: float | None = Field(default=None, gt=0, le=25)
    ganchillo_mm: float | None = Field(default=None, gt=0, le=25)
    # Ancho (cm) de una repeticion del grafico del panel de textura, medido en
    # la muestra lavada. Con este dato se compensa lo que cierran las trenzas.
    panel_motivo_cm: float | None = Field(default=None, gt=0, le=30)
    tecnica: Technique | None = None

    @field_validator("medidas_cm", "dimensiones_cm")
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
