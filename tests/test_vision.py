from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw

from vision.color import quantize_colors
from vision.preprocess import ImageValidationError, prepare_image
from vision.repeat import detect_repeat, fit_motif_width
from vision.segmentation import BorderColorSegmenter, NoopSegmenter


def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_prepare_image_resizes_and_strips_exif() -> None:
    image = Image.new("RGB", (2000, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 1900, 900), fill="navy")
    exif = Image.Exif()
    exif[274] = 6
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    prepared = prepare_image(buffer.getvalue())
    assert max(prepared.width, prepared.height) <= 1344
    assert prepared.width == 672
    assert prepared.height == 1344
    assert prepared.mime_type == "image/jpeg"
    assert prepared.original_format == "JPEG"
    assert prepared.crops
    reopened = Image.open(BytesIO(prepared.main))
    assert len(reopened.getexif()) == 0
    assert prepared.digest == prepare_image(buffer.getvalue()).digest


def test_prepare_image_keeps_small_image_and_skips_tiny_crops() -> None:
    prepared = prepare_image(png_bytes(Image.new("RGB", (40, 40), "white")))
    assert (prepared.width, prepared.height) == (40, 40)
    assert prepared.crops == {}


def test_prepare_image_rejects_invalid_and_unsupported() -> None:
    with pytest.raises(ImageValidationError):
        prepare_image(b"")
    with pytest.raises(ImageValidationError):
        prepare_image(b"not an image")
    buffer = BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="GIF")
    with pytest.raises(ImageValidationError):
        prepare_image(buffer.getvalue())


def test_quantize_colors_returns_palette_and_labels() -> None:
    image = Image.new("RGB", (60, 30), "red")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 0, 39, 29), fill="green")
    draw.rectangle((40, 0, 59, 29), fill="blue")
    result = quantize_colors(image, 3)
    assert len(result.palette) == 3
    assert result.labels.shape == (30, 60)
    assert sum(color.proportion for color in result.palette) == pytest.approx(1.0)
    assert all(color.hex.startswith("#") and len(color.hex) == 7 for color in result.palette)
    def close(rgb: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
        return max(abs(a - b) for a, b in zip(rgb, expected, strict=True)) <= 4

    assert any(close(color.rgb, (255, 0, 0)) for color in result.palette)
    assert any(close(color.rgb, (0, 128, 0)) for color in result.palette)
    assert any(close(color.rgb, (0, 0, 255)) for color in result.palette)


def test_quantize_colors_handles_more_colors_than_unique() -> None:
    image = Image.new("RGB", (20, 20), "white")
    result = quantize_colors(image, 8)
    assert len(result.palette) == 1
    assert result.palette[0].proportion == pytest.approx(1.0)


def test_detect_repeat_finds_stripes_and_checker() -> None:
    stripes = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(stripes)
    for x in range(0, 80, 8):
        draw.rectangle((x, 0, x + 3, 79), fill="black")
    pattern = detect_repeat(stripes, min_period=2)
    assert pattern.period_x == 8
    assert pattern.confidence_x > 0.9

    checker = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(checker)
    for y in range(0, 80, 8):
        for x in range(0, 80, 8):
            if (x // 8 + y // 8) % 2 == 0:
                draw.rectangle((x, y, x + 7, y + 7), fill="black")
    checker_pattern = detect_repeat(checker, min_period=2)
    assert checker_pattern.period_x == 16
    assert checker_pattern.period_y == 16


def test_fit_motif_width_uses_a_divisor() -> None:
    assert fit_motif_width(100, 8).width == 10
    assert fit_motif_width(100, 8).repeats == 10
    assert fit_motif_width(96, 8).width == 8
    assert fit_motif_width(96, 8).repeats == 12


def test_segmenters() -> None:
    image = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 69, 69), fill="red")
    mask = BorderColorSegmenter().segment(image)
    assert mask.shape == (100, 100)
    assert bool(mask[50, 50]) is True
    assert bool(mask[0, 0]) is False
    assert np.all(NoopSegmenter().segment(image))
