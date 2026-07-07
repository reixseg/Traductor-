"""Icono de bandeja del sistema."""

from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem


def _create_icon_image() -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, size - 4, size - 4), fill=(30, 120, 220, 255))
    draw.rectangle((18, 22, 46, 30), fill=(255, 255, 255, 255))
    draw.rectangle((18, 34, 40, 42), fill=(255, 255, 255, 220))
    return image


class TrayController:
    def __init__(
        self,
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_clear_cache: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_clear_cache = on_clear_cache
        self._on_quit = on_quit
        self._icon: Icon | None = None
        self._paused = False

    def _toggle_pause(self, _icon: Icon, _item: MenuItem) -> None:
        if self._paused:
            self._paused = False
            self._on_resume()
            if self._icon:
                self._icon.title = "Traductor en vivo — Activo"
        else:
            self._paused = True
            self._on_pause()
            if self._icon:
                self._icon.title = "Traductor en vivo — Pausado"

    def _quit(self, _icon: Icon, _item: MenuItem) -> None:
        if self._icon:
            self._icon.stop()
        self._on_quit()

    def run_in_background(self) -> None:
        menu = Menu(
            MenuItem("Pausar / Reanudar", self._toggle_pause, default=True),
            MenuItem("Limpiar caché de traducción", lambda *_: self._on_clear_cache()),
            Menu.SEPARATOR,
            MenuItem("Salir", self._quit),
        )
        self._icon = Icon(
            "live-translator",
            _create_icon_image(),
            "Traductor en vivo — Activo",
            menu,
        )
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def set_status(self, message: str) -> None:
        if self._icon:
            self._icon.title = message

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
