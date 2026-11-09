"""Catalogo declarativo de puntos.

Las exportaciones son perezosas para evitar un ciclo de importacion:
`engine.ir` necesita `engine.stitches.kinds`, y `catalog` necesita `Op`.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "STITCH_PATTERNS",
    "Effect",
    "StitchKind",
    "StitchPattern",
    "adjust_stitches",
    "catalog_id_for_name",
    "expand_row",
    "get_stitch",
    "stitch_effect",
    "validate_catalog",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from engine.stitches import catalog, kinds

        module = catalog if hasattr(catalog, name) else kinds
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
