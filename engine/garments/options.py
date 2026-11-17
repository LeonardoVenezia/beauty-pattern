"""Largos, escotes y estilos de manga comunes a todas las prendas con talle.

Antes cada familia tenia su copia de la tabla de largos; aca vive una sola
para que un largo nuevo (cintura, codo, vestido, saco) valga igual en todas.
Todos los valores son ASUNCIONES documentadas en docs/fuentes.md.
"""

from __future__ import annotations

from engine.garments.base import ImpossibleProportionsError
from engine.sizes import BodySize
from engine.spec import (
    BodyLength,
    Category,
    GarmentSpec,
    Neckline,
    Shape,
    SleeveLength,
    SleeveStyle,
)

# Largo del cuerpo (de la nuca al borde) respecto del largo a la cadera de la
# tabla de talles. ASUNCION: corto = 15 cm menos (min. 20), cintura = 10 cm
# menos, tunica = 8 cm mas, largo = 15 cm mas.
BODY_OFFSET_CM: dict[BodyLength, float] = {
    BodyLength.CROPPED: -15.0,
    BodyLength.WAIST: -10.0,
    BodyLength.HIP: 0.0,
    BodyLength.TUNIC: 8.0,
    BodyLength.LONG: 15.0,
}
# Vestido: ASUNCION a partir de proporciones corporales habituales (nuca a
# cadera ~58 cm, nuca a rodilla ~95 cm en el talle M): sin dato o a la
# cadera = a la rodilla (+37), tunica/corto = mini (+20), largo = midi (+55).
DRESS_OFFSET_CM: dict[BodyLength | None, float] = {
    None: 37.0,
    BodyLength.HIP: 37.0,
    BodyLength.CROPPED: 20.0,
    BodyLength.WAIST: 20.0,
    BodyLength.TUNIC: 20.0,
    BodyLength.LONG: 55.0,
}
# Saco/tapado: sin dato = a medio muslo (+15); largo = a la rodilla (+35).
COAT_DEFAULT_OFFSET_CM = 15.0
COAT_LONG_OFFSET_CM = 35.0

# Largo de manga (hombro a borde) como fraccion del largo a la muneca.
# ASUNCION: codo = 0,6 (el codo queda a ~0,55 del largo total y la manga lo
# cubre apenas); el resto ya estaba en uso desde el hito 2.
SLEEVE_FRACTION: dict[SleeveLength, float] = {
    SleeveLength.LONG: 1.0,
    SleeveLength.THREE_QUARTER: 0.75,
    SleeveLength.ELBOW: 0.6,
    SleeveLength.SHORT: 0.45,
}


def body_length_cm(spec: GarmentSpec, size: BodySize) -> float:
    """Largo total del cuerpo para la categoria y el largo vistos."""
    if spec.categoria is Category.DRESS:
        return size.body_length_cm + DRESS_OFFSET_CM.get(spec.largo_cuerpo, 37.0)
    if spec.categoria is Category.COAT and spec.largo_cuerpo in {None, BodyLength.LONG}:
        offset = COAT_LONG_OFFSET_CM if spec.largo_cuerpo is BodyLength.LONG else COAT_DEFAULT_OFFSET_CM
        return size.body_length_cm + offset
    length = spec.largo_cuerpo or BodyLength.HIP
    return max(20.0, size.body_length_cm + BODY_OFFSET_CM[length])


def has_sleeves(spec: GarmentSpec) -> bool:
    return effective_sleeve(spec) is not SleeveLength.SLEEVELESS


def effective_sleeve(spec: GarmentSpec) -> SleeveLength:
    """Largo de manga efectivo. Un top sin dato es una musculosa (ASUNCION:
    la forma mas comun de top tejido); la manga casquillo es corta."""
    if spec.estilo_manga is SleeveStyle.CAP:
        return SleeveLength.SHORT
    if spec.largo_manga is not None:
        return spec.largo_manga
    return SleeveLength.SLEEVELESS if spec.categoria is Category.TOP else SleeveLength.LONG


def sleeve_length_cm(spec: GarmentSpec, size: BodySize) -> float:
    length = effective_sleeve(spec)
    if length is SleeveLength.SLEEVELESS:
        raise ImpossibleProportionsError("error.unsupported_sleeve", length=length.value)
    return size.sleeve_length_cm * SLEEVE_FRACTION[length]


def sleeve_style(spec: GarmentSpec) -> SleeveStyle:
    return spec.estilo_manga or SleeveStyle.STRAIGHT


# Escotes. Holgura sobre el contorno de cuello de la tabla (cm). ASUNCION:
# barco +6, V/cuadrado +2, alto -1, capucha +4, redondo amplio (scoop) +8,
# cuello volcado (cowl) +6: tiene que caer sin apretar.
NECK_EXTRA_CM: dict[Neckline, float] = {
    Neckline.BOAT: 6.0,
    Neckline.V_NECK: 2.0,
    Neckline.SQUARE: 2.0,
    Neckline.TURTLENECK: -1.0,
    Neckline.FUNNEL: -1.0,
    Neckline.MOCK_NECK: 0.0,
    Neckline.HOOD: 4.0,
    Neckline.SCOOP: 8.0,
    Neckline.COWL_NECK: 6.0,
}
# Alto de la tira o del cuello (cm). ASUNCION: alto 8, medio alto (mock) 5,
# volcado 18 (cae en pliegues), cuello polo 7, scoop 2,5; el resto 3.
NECKBAND_CM: dict[Neckline, float] = {
    Neckline.TURTLENECK: 8.0,
    Neckline.FUNNEL: 8.0,
    Neckline.MOCK_NECK: 5.0,
    Neckline.COWL_NECK: 18.0,
    Neckline.POLO: 7.0,
    Neckline.SCOOP: 2.5,
}
# Profundidad del escote redondo del delantero (cm): 7 (rows.NECK_DEPTH_CM);
# el scoop baja a 12. ASUNCION.
NECK_DEPTH_CM: dict[Neckline, float] = {Neckline.SCOOP: 12.0}


A_LINE_FLARE = 1.25  # ASUNCION: borde 25 % mas ancho que el pecho (linea A)


def hem_circumference_cm(spec: GarmentSpec, size: BodySize, ease: float) -> float:
    """Contorno del borde inferior. El vestido tiene que pasar la cadera con
    la misma holgura que el pecho; la linea A (`forma=a_line`) ensancha el
    borde un 25 %. Sin nada de eso, el borde es el pecho."""
    target = size.bust_cm + ease
    if spec.categoria is not Category.DRESS and spec.forma is not Shape.A_LINE:
        return 0.0  # borde recto: sin forma
    if spec.categoria is Category.DRESS:
        target = max(target, size.hip_cm + ease)
    if spec.forma is Shape.A_LINE:
        target = max(target, (size.bust_cm + ease) * A_LINE_FLARE)
    return target


def neck_cm(spec: GarmentSpec, size: BodySize) -> float:
    return size.neck_cm + NECK_EXTRA_CM.get(spec.escote or Neckline.CREW, 0.0)


def neckband_cm(spec: GarmentSpec, default: float = 3.0) -> float:
    return NECKBAND_CM.get(spec.escote or Neckline.CREW, default)


def neck_depth_cm(spec: GarmentSpec, default: float = 7.0) -> float:
    return NECK_DEPTH_CM.get(spec.escote or Neckline.CREW, default)
