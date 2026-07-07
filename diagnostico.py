"""Diagnóstico rápido: captura, OCR y traducción."""

from __future__ import annotations

import json
import warnings

warnings.filterwarnings("ignore")

from capture import ScreenCapture
from ocr import OcrEngine
from translate import TextTranslator


def main() -> None:
    print("1. Capturando pantalla...")
    cap = ScreenCapture()
    image, monitor = cap.grab_primary()
    cap.close()
    path = "debug_captura.png"
    image.save(path)
    print(f"   Monitor: {monitor}")
    print(f"   Imagen: {image.size} -> {path}")

    print("2. Inicializando OCR (puede tardar)...")
    ocr = OcrEngine()
    blocks = ocr.detect(image, offset_x=monitor.left, offset_y=monitor.top)
    print(f"   Bloques detectados: {len(blocks)}")
    for i, b in enumerate(blocks[:8]):
        print(f"   [{i+1}] conf={b.confidence:.2f} | {b.text[:80]!r}")

    print("3. Probando traducción...")
    tr = TextTranslator()
    translated = 0
    for b in blocks[:10]:
        t = tr.translate_if_english(b.text)
        if t:
            translated += 1
            print(f"   EN: {b.text[:60]!r}")
            print(f"   ES: {t[:60]!r}")

    summary = {
        "monitor": monitor.__dict__,
        "image_size": image.size,
        "blocks_found": len(blocks),
        "sample_blocks": [b.text for b in blocks[:15]],
        "translated_count": translated,
    }
    with open("debug_resultado.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("4. Guardado debug_resultado.json")
    print("FIN")


if __name__ == "__main__":
    main()
