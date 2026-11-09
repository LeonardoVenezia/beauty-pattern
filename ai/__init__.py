"""Capa de IA del producto.

Un solo modelo (configurable por entorno) cumple los roles de extractor,
redactor y critico, con prompts y llamadas separadas. Ningun numero de un
patron se toma de estas respuestas.
"""

from ai.config import AIConfig
from ai.errors import AICapabilityError, AIConfigError, AIError

__all__ = ["AICapabilityError", "AIConfig", "AIConfigError", "AIError"]
