"""Ninguna foto se queda sin patron: ruta a la familia soportada mas cercana.

La IA puede ver cualquier tejido (maquina, guantes con dedos, un pullover de
construccion rara). En vez de fallar, se elige la familia verificada mas
parecida y el patron lo dice en una advertencia ("se aproximo X con Y").
"""

from __future__ import annotations

from engine.spec import (
    BodyLength,
    Category,
    Construction,
    GarmentSpec,
    MotifShape,
    Neckline,
    SleeveLength,
    Technique,
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
    Construction.MODIFIED_DROP_SHOULDER: Construction.DROP_SHOULDER,
    Construction.SADDLE_SHOULDER: Construction.SET_IN_SLEEVE,
    Construction.DOLMAN: Construction.DROP_SHOULDER,
    Construction.T_SHAPE: Construction.DROP_SHOULDER,
    Construction.SIDE_TO_SIDE: Construction.DROP_SHOULDER,
}

# Ampliacion D037: opciones que la IA ya reconoce pero que todavia no tienen
# calculo propio. Cada una va a la familia verificada mas parecida y el patron
# lo avisa ("warning.approx.<codigo>"). Al implementar una opcion, se borra
# de estas tablas.
CATEGORY_APPROX: dict[Category, Category] = {
    Category.TOP: Category.PULLOVER,
    Category.COAT: Category.CARDIGAN,
    Category.DRESS: Category.PULLOVER,
    Category.PONCHO: Category.SHAWL,
    Category.SHRUG: Category.CARDIGAN,
}
NECKLINE_APPROX: dict[Neckline, Neckline] = {
    Neckline.MOCK_NECK: Neckline.TURTLENECK,
    Neckline.SCOOP: Neckline.CREW,
    Neckline.HENLEY: Neckline.CREW,
    Neckline.POLO: Neckline.CREW,
    Neckline.SHAWL_COLLAR: Neckline.V_NECK,
    Neckline.COWL_NECK: Neckline.TURTLENECK,
}
BODY_LENGTH_APPROX: dict[BodyLength, BodyLength] = {BodyLength.WAIST: BodyLength.CROPPED}
SLEEVE_LENGTH_APPROX: dict[SleeveLength, SleeveLength] = {
    SleeveLength.ELBOW: SleeveLength.THREE_QUARTER
}
MOTIF_SHAPES_DONE: frozenset[MotifShape] = frozenset({MotifShape.CIRCLE, MotifShape.SQUARE})


def _approximate(spec: GarmentSpec, update: dict[str, object], notes: list[str]) -> None:
    """Opciones sin calculo propio -> la mas parecida, siempre avisando."""
    if spec.categoria in CATEGORY_APPROX:
        update["categoria"] = CATEGORY_APPROX[spec.categoria]
        notes.append("category")
    for field, table, code in (
        ("escote", NECKLINE_APPROX, "neckline"),
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
    if category is Category.PULLOVER and technique in _KNIT and spec.construccion in _PULLOVER:
        update["construccion"] = _PULLOVER[spec.construccion]
        if spec.construccion is not Construction.OTHER:
            notes.append("construction")
    update.update(tecnica=technique, categoria=category)
    return spec.model_copy(update=update), tuple(notes)
