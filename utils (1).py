"""Utilidades compartidas."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from statistics import median
from typing import Iterable

import numpy as np
from PIL import Image

from langdetect import DetectorFactory, LangDetectException, detect_langs

from config import CONFIG
from ocr import TextBlock


DetectorFactory.seed = 0

_LATIN_WORD = re.compile(r"[A-Za-zÀ-ÿ]{3,}")

# Palabras típicas de interfaz en español (no traducir).
_UI_SPANISH = re.compile(
    r"\b(archivo|editar|ver|ventana|ayuda|buscar|guardar|cerrar|abrir|configuración|"
    r"esperando|traducción|español|párrafo|pantalla|ventana|herramientas|formato)\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def detect_language(text: str) -> tuple[str, float]:
    try:
        langs = detect_langs(text)
        if langs:
            return langs[0].lang, float(langs[0].prob)
    except LangDetectException:
        pass
    return "unknown", 0.0


def needs_translation(text: str) -> bool:
    """True si el texto NO está en español y conviene traducirlo."""
    cleaned = normalize_text(text)
    if len(cleaned) < CONFIG.min_text_length:
        return False

    letters = sum(1 for c in cleaned if c.isalpha())
    if letters < 3:
        return False

    if not _LATIN_WORD.search(cleaned):
        return False

    if _UI_SPANISH.search(cleaned):
        lang, prob = detect_language(cleaned)
        if lang == "es" and prob >= 0.5:
            return False

    lang, prob = detect_language(cleaned)

    # Claramente español
    if lang == "es" and prob >= 0.7:
        return False

    # Claramente otro idioma
    if lang != "es" and lang != "unknown" and prob >= 0.55:
        return True

    # Texto largo: intentar traducir salvo que parezca español
    if len(cleaned) >= 14:
        return lang != "es" or prob < 0.45

    # Texto corto ambiguo: traducir si no parece español
    if lang == "unknown":
        return letters >= 5

    return lang != "es"


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def pick_readable_lines(blocks: list[TextBlock], min_length: int) -> list[TextBlock]:
    usable: list[TextBlock] = []
    for block in sorted(blocks, key=lambda b: (b.y, b.x)):
        text = normalize_text(block.text)
        if len(text) < min_length:
            continue
        if sum(1 for c in text if c.isalpha()) < 3:
            continue
        usable.append(
            TextBlock(
                text=text,
                confidence=block.confidence,
                x=block.x,
                y=block.y,
                width=block.width,
                height=block.height,
            )
        )
    return usable


def image_fingerprint(image) -> str:
    """Huella rápida para saltar OCR si la pantalla no cambió."""
    thumb = image.resize((96, 54)).convert("L")
    return hashlib.md5(thumb.tobytes(), usedforsecurity=False).hexdigest()


def _join_lines(texts: list[str]) -> str:
    """Une líneas de un párrafo, recomponiendo palabras cortadas con guion."""
    out = texts[0]
    for text in texts[1:]:
        if out.endswith("-") and text[:1].islower():
            out = out[:-1] + text
        else:
            out = f"{out} {text}"
    return out


def group_paragraphs(lines: list[TextBlock]) -> list[TextBlock]:
    """Une líneas apiladas del mismo párrafo para traducirlas con contexto."""
    if not getattr(CONFIG, "paragraph_mode", True):
        return list(lines)

    paragraphs: list[list[TextBlock]] = []
    for block in sorted(lines, key=lambda b: (b.y, b.x)):
        best: list[TextBlock] | None = None
        best_gap = 0.0

        for para in paragraphs:
            last = para[-1]
            h = max(last.height, block.height)
            gap = block.y - (last.y + last.height)

            if gap < -0.5 * h or gap > 0.6 * h:
                continue  # demasiado separada: otro párrafo
            ratio = block.height / max(1, last.height)
            if ratio < 0.6 or ratio > 1.65:
                continue  # tamaño de letra distinto (título, nota…)

            left = min(b.x for b in para)
            if block.x - left > 0.6 * h:
                continue  # sangría: empieza un párrafo nuevo
            if left - block.x > 2.0 * h:
                continue
            if block.x >= last.x + last.width or block.x + block.width <= last.x:
                continue  # no está debajo de la línea anterior
            if len(para) >= 2 and last.width < 0.6 * max(b.width for b in para):
                continue  # la línea anterior era corta: el párrafo terminó

            if best is None or gap < best_gap:
                best, best_gap = para, gap

        if best is None:
            paragraphs.append([block])
        else:
            best.append(block)

    result: list[TextBlock] = []
    for para in paragraphs:
        left = min(b.x for b in para)
        top = min(b.y for b in para)
        right = max(b.x + b.width for b in para)
        bottom = max(b.y + b.height for b in para)
        result.append(
            TextBlock(
                text=_join_lines([b.text for b in para]),
                confidence=min(b.confidence for b in para),
                x=left,
                y=top,
                width=max(1, right - left),
                height=max(1, bottom - top),
                line_height=int(median(b.height for b in para)),
                lines=len(para),
            )
        )
    return result


def image_thumbnail(image) -> np.ndarray:
    """Miniatura en grises para detectar cambios de pantalla."""
    small = image.resize((128, 72), Image.Resampling.BILINEAR).convert("L")
    return np.asarray(small, dtype=np.int16)


def thumb_diff(a: np.ndarray, b: np.ndarray) -> float:
    """Diferencia media (0-255) entre dos miniaturas."""
    return float(np.abs(a - b).mean())


def sample_background(image, blocks: list[TextBlock], origin_x: int, origin_y: int) -> list[TextBlock]:
    """Mide el color de fondo de cada bloque y elige un color de texto con contraste."""
    arr = np.asarray(image.convert("RGB"))
    height, width = arr.shape[:2]

    result: list[TextBlock] = []
    for block in blocks:
        x1 = max(0, block.x - origin_x)
        y1 = max(0, block.y - origin_y)
        x2 = min(width, x1 + block.width)
        y2 = min(height, y1 + block.height)
        if x2 - x1 < 2 or y2 - y1 < 2:
            result.append(block)
            continue

        patch = arr[y1:y2:2, x1:x2:2].reshape(-1, 3)

        # Color de fondo = el más frecuente (agrupando tonos casi iguales).
        quantized = (patch // 8).astype(np.int32)
        keys = quantized[:, 0] * 1024 + quantized[:, 1] * 32 + quantized[:, 2]
        values, counts = np.unique(keys, return_counts=True)
        dominant = keys == values[counts.argmax()]
        red, green, blue = (int(v) for v in patch[dominant].mean(axis=0))

        # El negro puro es el color transparente del overlay: se evita.
        if (red, green, blue) == (0, 0, 0):
            red = green = blue = 1

        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        fg = "#111111" if luminance >= 140 else "#F5F5F5"
        result.append(replace(block, bg=f"#{red:02X}{green:02X}{blue:02X}", fg=fg))
    return result
