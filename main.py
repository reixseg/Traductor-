"""
Traductor en vivo de pantalla — traducción superpuesta sobre el texto.
"""

from __future__ import annotations

import ctypes
import queue
import sys
import time
import traceback
import warnings

warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from capture import ScreenCapture
from config import CONFIG
from logger import LOGGER
from overlay import TranslationOverlay
from tray import TrayController
from worker import TranslationWorker, WorkerResult


def _show_startup_notice() -> None:
    if not CONFIG.show_startup_notice:
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Traductor iniciado correctamente.\n\n"
            "Las traducciones aparecerán SUPERPUESTAS sobre el texto en pantalla.\n"
            "Los clics pasan a través — puedes seguir usando el PDF o el juego.\n\n"
            "Icono azul en la bandeja (junto al reloj) para pausar o salir.\n"
            "Consejo: no uses pantalla completa.",
            "Traductor en vivo",
            0x40,
        )
    except Exception:
        pass


class LiveScreenTranslatorApp:
    def __init__(self) -> None:
        self._result_queue: queue.Queue[WorkerResult | None] = queue.Queue()
        self._worker = TranslationWorker(self._result_queue)
        self._overlay: TranslationOverlay | None = None
        self._tray: TrayController | None = None
        self._running = True
        self._last_raise = 0.0
        self._last_labels_result: WorkerResult | None = None
        LOGGER.info("Aplicacion iniciada")

    def _setup_overlay(self) -> None:
        capture = ScreenCapture()
        monitor = capture.get_monitor()
        capture.close()

        self._overlay = TranslationOverlay(
            monitor_left=monitor.left,
            monitor_top=monitor.top,
            width=monitor.width,
            height=monitor.height,
        )
        LOGGER.info("Overlay creado %sx%s en %s,%s", monitor.width, monitor.height, monitor.left, monitor.top)

    def _on_quit(self) -> None:
        self._running = False
        self._worker.stop()
        if self._overlay:
            self._overlay.request_quit()

    def _poll_results(self) -> None:
        while True:
            try:
                result = self._result_queue.get_nowait()
            except queue.Empty:
                break

            if result is None:
                self._running = False
                if self._overlay:
                    self._overlay.request_quit()
                break

            if result.status and self._tray:
                self._tray.set_status(f"Traductor en vivo — {result.status}")

            if not self._overlay:
                continue

            if result.translations:
                self._last_labels_result = result
                self._overlay.update_from_blocks(result.blocks, result.translations)

    def _tick(self) -> None:
        self._poll_results()

        now = time.time()
        if self._overlay and now - self._last_raise >= CONFIG.raise_interval_sec:
            self._overlay.raise_to_front()
            self._last_raise = now

        if self._running and self._overlay:
            self._overlay.schedule(self._tick)

    def run(self) -> int:
        try:
            self._setup_overlay()

            self._tray = TrayController(
                on_pause=self._worker.pause,
                on_resume=self._worker.resume,
                on_clear_cache=self._worker.clear_cache,
                on_quit=self._on_quit,
            )
            self._tray.run_in_background()
            self._tray.set_status("Traductor en vivo — Iniciando...")

            self._worker.start()

            if self._overlay:
                self._overlay.schedule(lambda: _show_startup_notice())
                self._overlay.schedule(self._tick)
                self._overlay.run_mainloop()
        except Exception:
            LOGGER.exception("Error fatal al iniciar")
            traceback.print_exc()
            return 1
        finally:
            if self._tray:
                self._tray.stop()
            if self._overlay:
                self._overlay.destroy()

        return 0


def main() -> int:
    return LiveScreenTranslatorApp().run()


if __name__ == "__main__":
    sys.exit(main())
