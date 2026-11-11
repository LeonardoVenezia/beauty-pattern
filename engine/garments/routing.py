"""Ninguna foto se queda sin patron: ruta a la familia soportada mas cercana.

La IA puede ver cualquier tejido (maquina, guantes con dedos, un pullover de
construccion rara). En vez de fallar, se elige la familia verificada mas
parecida y el patron lo dice en una advertencia ("se aproximo X con Y").
"""

from __future__ import annotations

from engine.spec import Category, Construction, GarmentSpec, Technique

_KNIT = {Technique.NEEDLES, Technique.CIRCULAR}
# Construcciones de pullover sin familia propia -> la mas parecida.
_PULLOVER = {
    Construction.BOTTOM_UP: Construction.SET_IN_SLEEVE,
    Construction.FLAT_PANELS: Construction.DROP_SHOULDER,
    Construction.IN_ONE_PIECE: Construction.RAGLAN_TOP_DOWN,
    Construction.ROUND_TUBE: Construction.RAGLAN_TOP_DOWN,
    Construction.MODULES: Construction.DROP_SHOULDER,
    Construction.OTHER: Construction.RAGLAN_TOP_DOWN,
}


def route(spec: GarmentSpec) -> tuple[GarmentSpec, tuple[str, ...]]:
    """(spec que se genera, codigos de aproximacion)."""
    notes: list[str] = []
    update: dict[str, object] = {}
    technique, category = spec.tecnica, spec.categoria
    if technique is Technique.MACHINE:
        technique = Technique.NEEDLES
        notes.append("machine")
    if technique is Technique.CROCHET and category in {Category.MITTENS, Category.GLOVES, Category.SOCKS}:
        technique = Technique.NEEDLES
        notes.append("crochet_to_knit")
    if technique in _KNIT and category is Category.AMIGURUMI:
        technique = Technique.CROCHET
        notes.append("knit_amigurumi")
    if technique in _KNIT and category is Category.GRANNY_SQUARE:
        category = Category.OTHER
        notes.append("knit_square")
    if category is Category.GLOVES:
        category = Category.MITTENS
        notes.append("gloves")
    if category is Category.PULLOVER and technique in _KNIT and spec.construccion in _PULLOVER:
        update["construccion"] = _PULLOVER[spec.construccion]
        if spec.construccion is not Construction.OTHER:
            notes.append("construction")
    update.update(tecnica=technique, categoria=category)
    return spec.model_copy(update=update), tuple(notes)
