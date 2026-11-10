"""Cuantizacion de color en espacio Lab y limpieza de pixeles aislados."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans


@dataclass(frozen=True)
class PaletteColor:
    rgb: tuple[int, int, int]
    hex: str
    proportion: float


@dataclass(frozen=True)
class ColorQuantization:
    palette: tuple[PaletteColor, ...]
    labels: np.ndarray
    width: int
    height: int


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _sample_pixels(pixels: np.ndarray, sample_size: int) -> np.ndarray:
    if len(pixels) <= sample_size:
        return pixels
    indexes = np.linspace(0, len(pixels) - 1, sample_size, dtype=np.int64)
    return pixels[indexes]


def quantize_colors(
    image: Image.Image,
    n_colors: int = 4,
    *,
    sample_size: int = 20_000,
    random_state: int = 0,
) -> ColorQuantization:
    """Cuantiza a `n_colors` colores en Lab y devuelve la paleta ordenada."""
    if n_colors < 1:
        raise ValueError("n_colors debe ser >= 1")
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width, _ = rgb.shape
    flat = rgb.reshape(-1, 3)
    sample = _sample_pixels(flat, sample_size)
    lab = cv2.cvtColor(sample.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    unique = np.unique(lab, axis=0)
    clusters = min(n_colors, len(unique))
    if clusters <= 1:
        labels_full = np.zeros(len(flat), dtype=np.uint8)
        center = flat.mean(axis=0).round().astype(np.uint8)
        palette = (
            PaletteColor(tuple(int(v) for v in center), _hex(tuple(int(v) for v in center)), 1.0),
        )
        return ColorQuantization(palette, labels_full.reshape(height, width), width, height)

    model = KMeans(n_clusters=clusters, random_state=random_state, n_init=10)
    model.fit(lab)
    full_lab = cv2.cvtColor(rgb.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    labels_full = model.predict(full_lab).astype(np.uint8)
    labels_image = labels_full.reshape(height, width)
    labels_image = cv2.medianBlur(labels_image, 3)
    labels_full = labels_image.reshape(-1)

    centers_rgb = cv2.cvtColor(
        np.clip(model.cluster_centers_, 0, 255).round().astype(np.uint8).reshape(-1, 1, 3),
        cv2.COLOR_LAB2RGB,
    ).reshape(-1, 3)
    counts = np.bincount(labels_full, minlength=clusters).astype(float)
    proportions = counts / counts.sum()
    order = np.argsort(-proportions)
    palette = tuple(
        PaletteColor(
            rgb=tuple(int(v) for v in centers_rgb[index]),
            hex=_hex(tuple(int(v) for v in centers_rgb[index])),
            proportion=float(proportions[index]),
        )
        for index in order
    )
    return ColorQuantization(palette, labels_image, width, height)
