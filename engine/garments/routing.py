"""Ninguna foto se queda sin patron: ruta a la familia soportada mas cercana.

La IA puede ver cualquier tejido (maquina, guantes con dedos, un pullover de
construccion rara). En vez de fallar, se elige la familia verificada mas
parecida y el patron lo dice en una advertencia ("se aproximo X con Y").
"""

from __future__ import annotations

from engine.garments.options import has_sleeves
from engine.spec import (
    BodyLength,
    Category,
    Construction,
    Figure,
    GarmentSpec,
    MotifShape,
    Neckline,
    SleeveLength,
    Technique,
    ToyBody,
)
from engine.stitches.catalog import APPROXIMATED_NAMES

_KNIT = {Technique.NEEDLES, Technique.CIRCULAR}
# Construcciones de pullover sin familia propia -> la mas parecida.
_PULLOVER = {
    Construction.BOTTOM_UP: Construction.SET_IN_SLEEVE,
    Construction.FLAT_PANELS: Construction.DROP_SHOULDER,
    Construction.IN_ONE_PIECE: Construction.RAGLAN_TOP_DOWN,
    Construction.ROUND_TUBE: Construction.RAGLAN_TOP_DOWN,
    Construction.MODULES: Construction.DROP_SHOULDER,
    Construction.OTHER: Construction.RAGLAN_TOP_DOWN,
    Construction.SADDLE_SHOULDER: Construction.SET_IN_SLEEVE,
    Construction.DOLMAN: Construction.DROP_SHOULDER,
    Construction.SIDE_TO_SIDE: Construction.DROP_SHOULDER,
}
# Construcciones que SON otra familia con otro nombre (sin aviso): la
# construccion en T son rectangulos cosidos, o sea hombro caido.
_SAME = {Construction.T_SHAPE: Construction.DROP_SHOULDER}
# Prendas que se calculan como pullover (con su largo y su titulo).
PULLOVER_LIKE = frozenset({Category.PULLOVER, Category.TOP, Category.DRESS})
CARDIGAN_LIKE = frozenset({Category.CARDIGAN, Category.COAT})
_ROUND = {Construction.RAGLAN_TOP_DOWN, Construction.YOKE}

# Ampliacion D037: opciones que la IA ya reconoce pero que todavia no tienen
# calculo propio. Cada una va a la familia verificada mas parecida y el patron
# lo avisa ("warning.approx.<codigo>"). Al implementar una opcion, se borra
# de estas tablas.
CATEGORY_APPROX: dict[Category, Category] = {
    Category.FINGERLESS_MITTS: Category.MITTENS,
    Category.BALACLAVA: Category.HAT,
    Category.HEADBAND: Category.COWL,
    Category.LEG_WARMERS: Category.COWL,
    Category.BOOTIES: Category.SOCKS,
    Category.SLIPPERS: Category.SOCKS,
    Category.FLAT_ITEM: Category.OTHER,
    Category.COZY: Category.BAG,
    Category.BASKET: Category.BAG,
    Category.PILLOW: Category.OTHER,
    Category.RUG: Category.OTHER,
}
NECKLINE_APPROX: dict[Neckline, Neckline] = {
    Neckline.MOCK_NECK: Neckline.TURTLENECK,
    Neckline.SCOOP: Neckline.CREW,
    Neckline.HENLEY: Neckline.CREW,
    Neckline.POLO: Neckline.CREW,
    Neckline.SHAWL_COLLAR: Neckline.V_NECK,
    Neckline.COWL_NECK: Neckline.TURTLENECK,
}
# Escotes con calculo propio en cada tipo de familia (garments, D038); el
# resto de NECKLINE_APPROX se aproxima en esa familia.
_NECK_ROUND = frozenset({Neckline.MOCK_NECK, Neckline.SCOOP, Neckline.COWL_NECK})
_NECK_FLAT = _NECK_ROUND | {Neckline.HENLEY, Neckline.POLO}
_NECK_CARDIGAN = _NECK_ROUND | {Neckline.SHAWL_COLLAR}
BODY_LENGTH_APPROX: dict[BodyLength, BodyLength] = {}
SLEEVE_LENGTH_APPROX: dict[SleeveLength, SleeveLength] = {}
TOY_FIGURES_DONE: frozenset[Figure] = frozenset(
    {Figure.BEAR, Figure.BUNNY, Figure.CAT, Figure.GENERIC}
)
TOY_BODIES_DONE: frozenset[ToyBody] = frozenset({ToyBody.PIECES, ToyBody.BALL})
MOTIF_SHAPES_DONE: frozenset[MotifShape] = frozenset({MotifShape.CIRCLE, MotifShape.SQUARE})


def _approximate(spec: GarmentSpec, update: dict[str, object], notes: list[str]) -> None:
    """Opciones sin calculo propio -> la mas parecida, siempre avisando."""
    if spec.categoria in CATEGORY_APPROX:
        update["categoria"] = CATEGORY_APPROX[spec.categoria]
        notes.append("category")
    for field, table, code in (
        ("largo_cuerpo", BODY_LENGTH_APPROX, "length"),
        ("largo_manga", SLEEVE_LENGTH_APPROX, "length"),
    ):
        value = getattr(spec, field)
        if value in table:
            update[field] = table[value]
            if code not in notes:
                notes.append(code)
    if spec.punto_base in APPROXIMATED_NAMES:
        notes.append("stitch")
    if spec.figura is not None and spec.figura not in TOY_FIGURES_DONE:
        update["figura"] = Figure.GENERIC
        notes.append("figure")
    if spec.cuerpo_juguete is not None and spec.cuerpo_juguete not in TOY_BODIES_DONE:
        update["cuerpo_juguete"] = ToyBody.PIECES
        notes.append("toy_body")
    if spec.motivo is not None and spec.motivo.forma not in MOTIF_SHAPES_DONE:
        update["motivo"] = spec.motivo.model_copy(update={"forma": MotifShape.CIRCLE})
        notes.append("motif_shape")


def route(spec: GarmentSpec) -> tuple[GarmentSpec, tuple[str, ...]]:
    """(spec que se genera, codigos de aproximacion)."""
    notes: list[str] = []
    update: dict[str, object] = {}
    _approximate(spec, update, notes)
    if update:
        spec = spec.model_copy(update=update)
    technique, category = spec.tecnica, spec.categoria
    if technique is Technique.MACHINE:
        technique = Technique.NEEDLES
        notes.append("machine")
    if technique is Technique.CROCHET and category in {
        Category.MITTENS,
        Category.GLOVES,
        Category.SOCKS,
    }:
        technique = Technique.NEEDLES
        notes.append("crochet_to_knit")
    if technique in _KNIT and category is Category.GRANNY_SQUARE:
        category = Category.OTHER
        notes.append("knit_square")
    if technique is Technique.CROCHET and category is Category.BLANKET and spec.motivo is not None:
        notes.append("blanket_motif")
    if category is Category.GLOVES:
        category = Category.MITTENS
        notes.append("gloves")
    construction = spec.construccion
    if category in PULLOVER_LIKE and technique in _KNIT:
        if construction in _SAME:
            construction = _SAME[construction]
        elif construction in _PULLOVER:
            construction = _PULLOVER[construction]
            if spec.construccion is not Construction.OTHER:
                notes.append("construction")
        if not has_sleeves(spec) and construction is not Construction.SET_IN_SLEEVE:
            # Sin mangas: piezas con sisa formada (la de manga encajada).
            if construction is not None:
                notes.append("sleeveless")
            construction = Construction.SET_IN_SLEEVE
        update["construccion"] = construction
    neck = _neckline(spec.escote, category, technique, construction)
    if neck is not spec.escote:
        update["escote"] = neck
        notes.append("neckline")
    update.update(tecnica=technique, categoria=category)
    return spec.model_copy(update=update), tuple(notes)


def _neckline(
    neck: Neckline | None, category: Category, technique: Technique, construction: Construction | None
) -> Neckline | None:
    """El escote, o el mas parecido si esa familia no lo calcula."""
    if neck not in NECKLINE_APPROX or category in {Category.SHRUG, Category.PONCHO}:
        return neck  # el poncho y el bolero no llevan escote
    supported: frozenset[Neckline] = frozenset()
    if technique in _KNIT and category in PULLOVER_LIKE | {Category.VEST}:
        supported = _NECK_ROUND if (construction or Construction.RAGLAN_TOP_DOWN) in _ROUND else _NECK_FLAT
        if category is Category.VEST:
            supported = _NECK_FLAT
    elif technique in _KNIT and category in CARDIGAN_LIKE:
        supported = _NECK_CARDIGAN
    return neck if neck in supported else NECKLINE_APPROX[neck]
