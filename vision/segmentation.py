"""Segmentacion intercambiable de la prenda.

La interfaz permite enchufar rembg/SAM mas adelante. La implementacion por
defecto es una heuristica de color de borde, sin modelos externos.
"""

from __future__ import annotations

from typing import Protocol

import cv2
import numpy as np
from PIL import Image


class Segmenter(Protocol):
    def segment(self, image: Image.Image) -> np.ndarray: ...


class NoopSegmenter:
    """Devuelve toda la imagen como prenda."""

    def segment(self, image: Image.Image) -> np.ndarray:
        return np.ones((image.height, image.width), dtype=bool)


class BorderColorSegmenter:
    """Separa la prenda del fondo usando el color dominante del borde."""

    def __init__(self, threshold: float = 42.0) -> None:
        self.threshold = threshold

    def segment(self, image: Image.Image) -> np.ndarray:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        height, width, _ = rgb.shape
        border = np.concatenate(
            [
                rgb[0, :, :],
                rgb[-1, :, :],
                rgb[:, 0, :],
                rgb[:, -1, :],
            ]
        )
        background = np.median(border, axis=0)
        distance = np.linalg.norm(rgb - background, axis=2)
        mask = (distance > self.threshold).astype(np.uint8)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        if count <= 1:
            return np.zeros((height, width), dtype=bool)
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return labels == largest
