"""Errores comunes de las familias de prendas."""

from __future__ import annotations


class GarmentError(Exception):
    """Error de generacion con una clave de traduccion y parametros."""

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params: dict[str, object] = params
        super().__init__(key)


class UnsupportedGarmentError(GarmentError):
    """La prenda o la tecnica no pertenecen a esta familia."""


class ImpossibleProportionsError(GarmentError):
    """Las medidas pedidas no cierran para esta construccion."""
