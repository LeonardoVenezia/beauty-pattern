"""Preprocesado obligatorio de la foto antes de enviarla a la IA.

Corrige la orientacion EXIF, elimina metadatos, limita el lado mayor a 1344 px
y genera recortes de detalle. Nada de esto decide atributos: solo prepara la
entrada para que el modelo vea lo mejor posible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1344
MAX_PIXELS = 40_000_000
MIN_CROP_SIDE = 48
JPEG_QUALITY = 90

CROP_FRACTIONS: dict[str, tuple[float, float, float, float]] = {
    "chest": (0.22, 0.04, 0.78, 0.42),
    "cuff": (0.05, 0.62, 0.42, 0.98),
    "texture": (0.28, 0.35, 0.72, 0.78),
}


class ImageValidationError(ValueError):
    """La imagen no se puede procesar de forma segura."""


@dataclass(frozen=True)
class PreparedImage:
    main: bytes
    mime_type: str
    width: int
    height: int
    crops: dict[str, bytes]
    digest: str
    original_format: str


def _clean_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, "white")
        alpha = image.getchannel("A")
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _encode_jpeg(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def _crop(image: Image.Image, fraction: tuple[float, float, float, float]) -> bytes | None:
    width, height = image.size
    left, top, right, bottom = fraction
    box = (
        max(0, int(left * width)),
        max(0, int(top * height)),
        min(width, int(right * width)),
        min(height, int(bottom * height)),
    )
    if box[2] - box[0] < MIN_CROP_SIDE or box[3] - box[1] < MIN_CROP_SIDE:
        return None
    crop = image.crop(box)
    if max(crop.size) > MAX_SIDE:
        crop.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return _encode_jpeg(crop)


def prepare_image(
    data: bytes,
    *,
    max_side: int = MAX_SIDE,
    max_pixels: int = MAX_PIXELS,
) -> PreparedImage:
    """Valida, orienta, limpia y redimensiona la imagen; devuelve recortes."""
    if not data:
        raise ImageValidationError("la imagen esta vacia")
    try:
        with Image.open(BytesIO(data)) as source:
            original_format = (source.format or "").upper()
            if original_format not in {"JPEG", "PNG", "WEBP"}:
                raise ImageValidationError(
                    f"formato de imagen no soportado: {original_format or 'desconocido'}"
                )
            if source.width * source.height > max_pixels:
                raise ImageValidationError("la imagen tiene demasiados pixeles")
            source.load()
            oriented = ImageOps.exif_transpose(source)
            image = _clean_rgb(oriented)
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            crops: dict[str, bytes] = {}
            for name, fraction in CROP_FRACTIONS.items():
                crop = _crop(image, fraction)
                if crop is not None:
                    crops[name] = crop
            return PreparedImage(
                main=_encode_jpeg(image),
                mime_type="image/jpeg",
                width=image.width,
                height=image.height,
                crops=crops,
                digest=hashlib.sha256(data).hexdigest(),
                original_format=original_format,
            )
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("no se pudo leer la imagen") from exc


def prepare_image_bytes(data: bytes) -> bytes:
    """Atajo para tests y llamadas que solo necesitan la imagen principal."""
    return prepare_image(data).main
