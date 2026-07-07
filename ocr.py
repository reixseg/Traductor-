"""Motor OCR rápido (RapidOCR / ONNX)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from config import CONFIG


@dataclass(frozen=True)
class TextBlock:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


class OcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._reader = RapidOCR()

    def _downscale(self, image: Image.Image) -> tuple[Image.Image, float]:
        width, height = image.size
        max_width = CONFIG.ocr_max_width
        if width <= max_width:
            return image, 1.0

        scale = max_width / width
        resized = image.resize(
            (max_width, max(1, int(height * scale))),
            Image.Resampling.BILINEAR,
        )
        return resized, 1.0 / scale

    def detect(self, image: Image.Image, offset_x: int = 0, offset_y: int = 0) -> list[TextBlock]:
        small, coord_scale = self._downscale(image.convert("RGB"))
        rgb = np.array(small)
        raw, _elapsed = self._reader(rgb)

        blocks: list[TextBlock] = []
        if not raw:
            return blocks

        for item in raw:
            if len(item) < 3:
                continue

            bbox, text, confidence = item[0], item[1], float(item[2])
            text = str(text).strip()
            if not text or confidence < CONFIG.ocr_confidence:
                continue

            xs = [int(p[0] * coord_scale) for p in bbox]
            ys = [int(p[1] * coord_scale) for p in bbox]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)

            blocks.append(
                TextBlock(
                    text=text,
                    confidence=confidence,
                    x=offset_x + x1,
                    y=offset_y + y1,
                    width=max(1, x2 - x1),
                    height=max(1, y2 - y1),
                )
            )

        return blocks
