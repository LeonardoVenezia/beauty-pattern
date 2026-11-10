"""Capa de IA del producto.

Un solo modelo (configurable por entorno) cumple los roles de extractor,
redactor y critico, con prompts y llamadas separadas. Ningun numero de un
patron se toma de estas respuestas.
"""

from ai.config import AIConfig
from ai.critic import CriticResult, critique_pattern
from ai.errors import AICapabilityError, AIConfigError, AIError, ExtractionError
from ai.extractor import ExtractionResult, extract_garment
from ai.writer import WriterResult, write_pattern_text

__all__ = [
    "AICapabilityError",
    "AIConfig",
    "AIConfigError",
    "AIError",
    "CriticResult",
    "ExtractionError",
    "ExtractionResult",
    "WriterResult",
    "critique_pattern",
    "extract_garment",
    "write_pattern_text",
]
