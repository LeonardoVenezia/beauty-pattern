"""Errores de la capa de IA."""

from __future__ import annotations


class AIError(Exception):
    """Error generico de la capa de IA."""


class AIConfigError(AIError):
    """Falta configuracion o es invalida."""


class AICapabilityError(AIError):
    """El endpoint no soporta una capacidad requerida (por ejemplo, imagenes)."""


class AIResponseError(AIError):
    """La respuesta no tiene el formato esperado."""


class ExtractionError(AIError):
    """No se pudo obtener una extraccion valida tras los reintentos."""
