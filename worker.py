"""Bucle de trabajo en segundo plano: captura → OCR → traducción."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto

from capture import ScreenCapture
from config import CONFIG
from logger import LOGGER
from ocr import OcrEngine, TextBlock
from translate import TextTranslator
from utils import dedupe_preserve_order, image_fingerprint, pick_readable_lines


class WorkerCommand(Enum):
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    CLEAR_CACHE = auto()


@dataclass
class WorkerResult:
    blocks: list[TextBlock]
    translations: dict[str, str]
    status: str | None = None


class TranslationWorker:
    def __init__(self, result_queue: queue.Queue[WorkerResult | None]) -> None:
        self._result_queue = result_queue
        self._command_queue: queue.Queue[WorkerCommand] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._paused = False
        self._running = False
        self._last_fingerprint: str | None = None
        self._last_good_result: WorkerResult | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="translation-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._command_queue.put(WorkerCommand.STOP)

    def pause(self) -> None:
        self._paused = True
        self._command_queue.put(WorkerCommand.PAUSE)

    def resume(self) -> None:
        self._paused = False
        self._command_queue.put(WorkerCommand.RESUME)

    def clear_cache(self) -> None:
        self._command_queue.put(WorkerCommand.CLEAR_CACHE)

    def _status(self, message: str) -> None:
        self._result_queue.put(WorkerResult(blocks=[], translations={}, status=message))

    def _drain_commands(self, translator: TextTranslator) -> bool:
        while True:
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                break

            if cmd == WorkerCommand.STOP:
                return False
            if cmd == WorkerCommand.PAUSE:
                self._paused = True
            elif cmd == WorkerCommand.RESUME:
                self._paused = False
            elif cmd == WorkerCommand.CLEAR_CACHE:
                translator.clear_cache()
                self._last_fingerprint = None
                self._last_good_result = None
                self._status("Caché limpiada")

        return True

    def _run(self) -> None:
        capture = ScreenCapture()
        translator: TextTranslator | None = None
        ocr: OcrEngine | None = None
        cycle = 0

        try:
            self._status("Esperando inicio del OCR...")
            time.sleep(CONFIG.ocr_startup_delay)

            self._status("Cargando traducción offline (la primera vez descarga el idioma)...")
            translator = TextTranslator()
            translator.warmup()
            LOGGER.info("Traductor Argos listo")

            self._status("Inicializando OCR (primera vez puede tardar)...")
            ocr = OcrEngine()
            LOGGER.info("OCR RapidOCR listo")
            self._status("Activo — detectando idiomas en pantalla...")

            while self._running:
                if not self._drain_commands(translator):
                    break

                if self._paused:
                    time.sleep(0.2)
                    continue

                cycle += 1
                started = time.perf_counter()
                image, region = capture.grab_content()

                if CONFIG.skip_unchanged_screen:
                    fp = image_fingerprint(image)
                    if fp == self._last_fingerprint and self._last_good_result:
                        self._result_queue.put(self._last_good_result)
                        time.sleep(CONFIG.min_sleep_after_cycle)
                        continue
                    self._last_fingerprint = fp

                ocr_started = time.perf_counter()
                raw_blocks = ocr.detect(image, offset_x=region.left, offset_y=region.top)
                ocr_time = time.perf_counter() - ocr_started

                lines = pick_readable_lines(raw_blocks, CONFIG.min_line_length)
                texts = [line.text for line in lines[: CONFIG.max_lines_per_cycle]]

                translate_started = time.perf_counter()
                translations = translator.translate_many(texts)
                translate_time = time.perf_counter() - translate_started

                unique_translations = dedupe_preserve_order(translations.values())
                elapsed = time.perf_counter() - started

                LOGGER.info(
                    "ciclo=%s bloques=%s lineas=%s traducciones=%s tiempo=%.1fs (ocr=%.1fs trad=%.1fs)",
                    cycle,
                    len(raw_blocks),
                    len(lines),
                    len(unique_translations),
                    elapsed,
                    ocr_time,
                    translate_time,
                )

                if translations:
                    translated_blocks = [b for b in lines if b.text in translations]
                    result = WorkerResult(
                        blocks=translated_blocks,
                        translations=translations,
                        status=f"{len(unique_translations)} línea(s) · {elapsed:.1f}s",
                    )
                    self._last_good_result = result
                    self._result_queue.put(result)
                else:
                    # Sin traducciones: no reutilizar un resultado viejo.
                    self._last_good_result = None
                    if translator.last_error:
                        self._status(f"Error de traducción: {translator.last_error}")
                    elif lines:
                        self._status(f"OCR: {len(lines)} línea(s) ya en español o sin cambios")
                    elif raw_blocks:
                        self._status(f"OCR: {len(raw_blocks)} fragmento(s) detectados")
                    else:
                        self._status("Sin texto legible en pantalla")

                sleep_for = max(CONFIG.min_sleep_after_cycle, CONFIG.capture_interval - elapsed)
                time.sleep(sleep_for)

        except Exception as exc:
            LOGGER.exception("Error en worker: %s", exc)
            self._status(f"Error: {exc}")
        finally:
            if translator:
                translator.shutdown()
            capture.close()
            self._running = False
            self._result_queue.put(None)
