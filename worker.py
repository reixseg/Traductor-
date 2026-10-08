"""Bucle de trabajo en segundo plano: captura → OCR → traducción."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from capture import ScreenCapture
from config import CONFIG
from logger import LOGGER
from ocr import OcrEngine, TextBlock
from translate import TextTranslator
from utils import (
    dedupe_preserve_order,
    group_paragraphs,
    image_thumbnail,
    pick_readable_lines,
    sample_background,
    thumb_diff,
)


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
        self._watcher: threading.Thread | None = None
        self._paused = False
        self._running = False
        self._last_good_result: WorkerResult | None = None

        # Detección de cambios de pantalla
        self._last_thumb: np.ndarray | None = None  # última pantalla procesada
        self._reference_thumb: np.ndarray | None = None  # pantalla a la que corresponde el overlay
        self._screen_changed = False

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
                self._last_thumb = None
                self._last_good_result = None
                self._status("Caché limpiada")

        return True

    # ------------------------------------------------------------------
    # Vigilante: limpia el overlay en cuanto la pantalla cambia
    # ------------------------------------------------------------------
    def _watch_changes(self) -> None:
        capture = ScreenCapture()  # mss debe crearse en el hilo que lo usa
        try:
            while self._running:
                time.sleep(CONFIG.stable_check_interval)
                reference = self._reference_thumb
                if self._paused or reference is None or self._screen_changed:
                    continue

                thumb = image_thumbnail(capture.grab_content()[0])
                if thumb_diff(thumb, reference) > CONFIG.change_threshold:
                    self._screen_changed = True
                    self._status("Pantalla cambió — actualizando...")
        except Exception:
            LOGGER.exception("Error en el vigilante de cambios de pantalla")
        finally:
            capture.close()

    def _wait_until_stable(self, capture: ScreenCapture, image, region, thumb):
        """Espera a que termine el scroll / cambio de página antes de hacer OCR."""
        deadline = time.perf_counter() + CONFIG.stable_wait_max
        while self._running and time.perf_counter() < deadline:
            time.sleep(CONFIG.stable_check_interval)
            image2, region2 = capture.grab_content()
            thumb2 = image_thumbnail(image2)
            stable = thumb_diff(thumb, thumb2) <= CONFIG.change_threshold
            image, region, thumb = image2, region2, thumb2
            if stable:
                break
        return image, region, thumb

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
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

            self._watcher = threading.Thread(
                target=self._watch_changes, name="screen-watcher", daemon=True
            )
            self._watcher.start()

            while self._running:
                if not self._drain_commands(translator):
                    break

                if self._paused:
                    time.sleep(0.2)
                    continue

                image, region = capture.grab_content()
                thumb = image_thumbnail(image)

                # Pantalla sin cambios: no repetir OCR, solo mantener lo mostrado.
                if (
                    CONFIG.skip_unchanged_screen
                    and self._last_thumb is not None
                    and thumb_diff(thumb, self._last_thumb) <= CONFIG.change_threshold
                ):
                    self._screen_changed = False
                    if self._last_good_result:
                        self._result_queue.put(self._last_good_result)
                    time.sleep(CONFIG.min_sleep_after_cycle)
                    continue

                image, region, thumb = self._wait_until_stable(capture, image, region, thumb)
                self._last_thumb = thumb
                self._reference_thumb = thumb
                self._screen_changed = False

                cycle += 1
                started = time.perf_counter()

                ocr_started = time.perf_counter()
                raw_blocks = ocr.detect(image, offset_x=region.left, offset_y=region.top)
                ocr_time = time.perf_counter() - ocr_started

                lines = pick_readable_lines(raw_blocks, 1)
                paragraphs = [
                    p
                    for p in group_paragraphs(lines[: CONFIG.max_lines_per_cycle])
                    if len(p.text) >= CONFIG.min_line_length
                ]
                texts = [p.text for p in paragraphs]

                translate_started = time.perf_counter()
                translations = translator.translate_many(texts)
                translate_time = time.perf_counter() - translate_started

                unique_translations = dedupe_preserve_order(translations.values())
                elapsed = time.perf_counter() - started

                LOGGER.info(
                    "ciclo=%s bloques=%s lineas=%s parrafos=%s traducciones=%s tiempo=%.1fs (ocr=%.1fs trad=%.1fs)",
                    cycle,
                    len(raw_blocks),
                    len(lines),
                    len(paragraphs),
                    len(unique_translations),
                    elapsed,
                    ocr_time,
                    translate_time,
                )

                # La pantalla cambió mientras procesábamos: este resultado ya es viejo.
                if self._screen_changed:
                    LOGGER.info("ciclo=%s descartado: la pantalla cambió durante el proceso", cycle)
                    self._last_thumb = None
                    self._last_good_result = None
                    continue

                if translations:
                    translated_blocks = [b for b in paragraphs if b.text in translations]
                    if CONFIG.overlay_match_background:
                        translated_blocks = sample_background(
                            image, translated_blocks, region.left, region.top
                        )
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
            self._running = False
            if translator:
                translator.shutdown()
            capture.close()
            self._result_queue.put(None)
