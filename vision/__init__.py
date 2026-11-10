"""Vision por computadora clasica."""

from vision.color import ColorQuantization, PaletteColor, quantize_colors
from vision.preprocess import (
    ImageValidationError,
    PreparedImage,
    prepare_image,
    prepare_image_bytes,
)
from vision.repeat import MotifFit, RepeatPattern, detect_repeat, fit_motif_width
from vision.segmentation import (
    BorderColorSegmenter,
    NoopSegmenter,
    Segmenter,
)

__all__ = [
    "BorderColorSegmenter",
    "ColorQuantization",
    "ImageValidationError",
    "MotifFit",
    "NoopSegmenter",
    "PaletteColor",
    "PreparedImage",
    "RepeatPattern",
    "Segmenter",
    "detect_repeat",
    "fit_motif_width",
    "prepare_image",
    "prepare_image_bytes",
    "quantize_colors",
]
