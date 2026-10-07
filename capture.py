"""Captura de pantalla sin bloquear la interacción del usuario."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import mss # type: ignore
from PIL import Image


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int


def get_work_area() -> tuple[int, int, int, int]:
    """Área usable de Windows (excluye la barra de tareas)."""
    rect = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def clip_to_work_area(monitor: MonitorInfo) -> MonitorInfo:
    """Recorta el monitor para no cubrir ni capturar la barra de tareas."""
    wa_left, wa_top, wa_width, wa_height = get_work_area()
    wa_right = wa_left + wa_width
    wa_bottom = wa_top + wa_height

    mon_right = monitor.left + monitor.width
    mon_bottom = monitor.top + monitor.height

    left = max(monitor.left, wa_left)
    top = max(monitor.top, wa_top)
    right = min(mon_right, wa_right)
    bottom = min(mon_bottom, wa_bottom)

    return MonitorInfo(
        index=monitor.index,
        left=left,
        top=top,
        width=max(1, right - left),
        height=max(1, bottom - top),
    )


class ScreenCapture:
    def __init__(self, monitor_index: int = 1) -> None:
        self._monitor_index = monitor_index
        self._sct = mss.mss()

    def get_monitor(self) -> MonitorInfo:
        monitors = self._sct.monitors
        idx = min(self._monitor_index, len(monitors) - 1)
        mon = monitors[idx]
        full = MonitorInfo(
            index=idx,
            left=mon["left"],
            top=mon["top"],
            width=mon["width"],
            height=mon["height"],
        )
        return clip_to_work_area(full)

    def _get_capture_box(self, monitor: MonitorInfo) -> dict[str, int]:
        from config import CONFIG

        capture_region = CONFIG.capture_region or {}
        if not capture_region.get("enabled"):
            return {
                "left": monitor.left,
                "top": monitor.top,
                "width": monitor.width,
                "height": monitor.height,
            }

        left = int(capture_region.get("left", 0))
        top = int(capture_region.get("top", 0))
        width = int(capture_region.get("width", monitor.width))
        height = int(capture_region.get("height", monitor.height))
        return {
            "left": monitor.left + left,
            "top": monitor.top + top,
            "width": max(1, min(width, monitor.width - left)),
            "height": max(1, min(height, monitor.height - top)),
        }

    def grab_primary(self) -> tuple[Image.Image, MonitorInfo]:
        monitor = self.get_monitor()
        box = self._get_capture_box(monitor)
        shot = self._sct.grab(
            {
                "left": box["left"],
                "top": box["top"],
                "width": box["width"],
                "height": box["height"],
            }
        )
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        region = MonitorInfo(
            index=monitor.index,
            left=box["left"],
            top=box["top"],
            width=box["width"],
            height=box["height"],
        )
        return image, region

    def grab_content(self) -> tuple[Image.Image, MonitorInfo]:
        """Captura la zona de lectura (sin barra de tareas ni menús superiores)."""
        from config import CONFIG

        image, monitor = self.grab_primary()
        top = CONFIG.content_top_margin
        bottom = CONFIG.content_bottom_margin
        left = CONFIG.content_left_margin
        right = 20

        crop_left = min(left, monitor.width - 2)
        crop_right = max(crop_left + 1, monitor.width - right)
        crop_bottom = max(top + 1, monitor.height - bottom)

        cropped = image.crop((crop_left, top, crop_right, crop_bottom))
        region = MonitorInfo(
            index=monitor.index,
            left=monitor.left + crop_left,
            top=monitor.top + top,
            width=crop_right - crop_left,
            height=crop_bottom - top,
        )
        return cropped, region

    def close(self) -> None:
        self._sct.close()
