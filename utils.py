"""Utilidades compartidas."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

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
