"""Overlay superpuesto estilo subtítulo (sin cajas blancas)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

import win32api
import win32con
import win32gui

from config import CONFIG
from ocr import TextBlock


@dataclass(frozen=True)
class OverlayLabel:
    x: int
    y: int
    text: str
    width: int
    height: int


class TranslationOverlay:
    def __init__(self, monitor_left: int, monitor_top: int, width: int, height: int) -> None:
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.configure(bg="black")

        self._left = monitor_left
        self._top = monitor_top
        self._width = width
        self._height = height

        self._root.geometry(f"{width}x{height}+{monitor_left}+{monitor_top}")
        self._root.attributes("-transparentcolor", "black")

        self._canvas = tk.Canvas(
            self._root,
            width=width,
            height=height,
            bg="black",
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        self._visible = False
        self._font = ("Segoe UI", CONFIG.overlay_font_size)
        self._root.update_idletasks()
        self._apply_window_styles()

    def _hwnd(self) -> int:
        return self._root.winfo_id()

    def _apply_window_styles(self) -> None:
        hwnd = self._hwnd()
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE
        if CONFIG.click_through:
            style |= win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)

    def _raise_above_apps(self) -> None:
        hwnd = self._hwnd()
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            self._left,
            self._top,
            self._width,
            self._height,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )
        self._apply_window_styles()

    def show(self) -> None:
        if not self._visible:
            self._root.deiconify()
            self._visible = True
        self._root.update_idletasks()
        self._raise_above_apps()

    def hide(self) -> None:
        if self._visible:
            self._root.withdraw()
            self._visible = False

    def clear(self) -> None:
        self._canvas.delete("all")

    def _draw_subtitle(self, x: int, y: int, text: str, max_width: int) -> None:
        """Texto con contorno suave, sin caja blanca."""
        wrap_w = min(max_width + 40, CONFIG.overlay_max_width)
        outline = CONFIG.overlay_outline_color
        fill = CONFIG.overlay_text_color

        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self._canvas.create_text(
                x + dx,
                y + dy,
                text=text,
                anchor="nw",
                fill=outline,
                font=self._font,
                width=wrap_w,
            )

        self._canvas.create_text(
            x,
            y,
            text=text,
            anchor="nw",
            fill=fill,
            font=self._font,
            width=wrap_w,
        )

    def _group_labels(self, blocks: list[TextBlock], translations: dict[str, str]) -> list[OverlayLabel]:
        """Agrupa palabras de la misma línea en una sola frase."""
        band = CONFIG.overlay_line_group_px
        rows: dict[int, list[tuple[TextBlock, str]]] = {}

        for block in blocks:
            translated = translations.get(block.text)
            if not translated:
                continue
            key = block.y // band
            rows.setdefault(key, []).append((block, translated))

        labels: list[OverlayLabel] = []
        for items in sorted(rows.values(), key=lambda row: row[0][0].y):
            items.sort(key=lambda item: item[0].x)
            first = items[0][0]
            parts: list[str] = []
            for block, tr in items:
                if not parts or parts[-1] != tr:
                    parts.append(tr)

            combined = " ".join(parts)
            right = max(b.x + b.width for b, _ in items)
            bottom = max(b.y + b.height for b, _ in items)
            labels.append(
                OverlayLabel(
                    x=first.x,
                    y=first.y,
                    text=combined,
                    width=max(1, right - first.x),
                    height=max(1, bottom - first.y),
                )
            )
        return labels

    def render(self, labels: list[OverlayLabel]) -> None:
        self.clear()
        if not labels:
            if CONFIG.hide_when_empty:
                self.hide()
            return

        self.show()
        for label in labels[: CONFIG.max_overlay_blocks]:
            x = label.x - self._left
            y = label.y - self._top

            if x < -80 or y < -80 or x > self._width + 80 or y > self._height + 80:
                continue

            self._draw_subtitle(x, y, label.text, label.width)

    def update_from_blocks(self, blocks: list[TextBlock], translations: dict[str, str]) -> None:
        labels = self._group_labels(blocks, translations)
        self.render(labels)

    def schedule(self, callback) -> None:
        self._root.after(CONFIG.ui_poll_ms, callback)

    def request_quit(self) -> None:
        self._root.after(0, self._root.quit)

    def run_mainloop(self) -> None:
        self._root.mainloop()

    def destroy(self) -> None:
        self._root.destroy()

    def raise_to_front(self) -> None:
        self._raise_above_apps()
