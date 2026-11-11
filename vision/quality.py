"""Chequeo determinista de calidad de la foto (antes de la IA).

No decide nada sobre la prenda: solo avisa cuando la foto puede esconder
detalles (borrosa, chica, oscura, quemada), para que la persona sepa que
conviene sumar otra foto y para que el prompt le pida prudencia al modelo.

ASUNCION: umbrales calibrados a ojo sobre fotos de celular redimensionadas a
<= 1344 px; ver docs/fuentes.md.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

MIN_SIDE_PX = 480
BLUR_VARIANCE = 40.0  # varianza del laplaciano en gris (0-255) a 512 px
DARK_MEAN = 55.0
BRIGHT_MEAN = 215.0


def assess_quality(image: Image.Image) -> tuple[str, ...]:
    """Codigos de problema: "small", "blurry", "dark", "bright"."""
    issues: list[str] = []
    if min(image.size) < MIN_SIDE_PX:
        issues.append("small")
    gray = image.convert("L")
    gray.thumbnail((512, 512))
    pixels = np.asarray(gray, dtype=np.float64)
    if pixels.shape[0] >= 3 and pixels.shape[1] >= 3:
        lap = (
            pixels[:-2, 1:-1] + pixels[2:, 1:-1] + pixels[1:-1, :-2] + pixels[1:-1, 2:]
            - 4 * pixels[1:-1, 1:-1]
        )
        if float(lap.var()) < BLUR_VARIANCE:
            issues.append("blurry")
    mean = float(pixels.mean())
    if mean < DARK_MEAN:
        issues.append("dark")
    elif mean > BRIGHT_MEAN:
        issues.append("bright")
    return tuple(issues)
