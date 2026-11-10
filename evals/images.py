"""Imagenes sinteticas para que `make eval` corra sin fotos externas.

Son marcadores de posicion honestos: sirven para probar el flujo, la votacion
y el reporte, no para medir vision real. Reemplazar por fotos en `evals/`.
"""

from __future__ import annotations

import random
from io import BytesIO

from PIL import Image, ImageDraw


def synthetic_case_image(seed: int, width: int = 640, height: int = 800) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height), (238, 235, 228))
    draw = ImageDraw.Draw(image)
    body = (60 + seed * 20, 80 + seed * 10, 130 + seed * 15)
    sleeve = tuple(max(0, value - 25) for value in body)
    draw.rectangle((width // 2 - 110, 180, width // 2 + 110, height - 90), fill=body)
    draw.rectangle((width // 2 - 230, 200, width // 2 - 110, 560), fill=sleeve)
    draw.rectangle((width // 2 + 110, 200, width // 2 + 230, 560), fill=sleeve)
    draw.ellipse((width // 2 - 55, 150, width // 2 + 55, 230), fill=(220, 220, 220))
    for y in range(260, height - 100, 24):
        color = (body[0] + 20, body[1] + 20, body[2] + 20)
        draw.line((width // 2 - 105, y, width // 2 + 105, y), fill=color, width=2)
    for _ in range(80):
        x = rng.randrange(0, width)
        y = rng.randrange(0, height)
        draw.point((x, y), fill=(200, 200, 200))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
