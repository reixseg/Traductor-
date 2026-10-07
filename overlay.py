"""Overlay superpuesto: cubre el texto original con su traducción."""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass

import win32api
import win32con
import win32gui

from config import CONFIG
from logger import LOGGER
from ocr import TextBlock

# Windows 10 versión 2004 (build 19041) o superior.
WDA_EXCLUDEFROMCAPTURE = 0x00000011


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
            bg="black",  # color transparente: NO usarlo en cajas ni texto
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        self._visible = False
        self._last_labels: list[OverlayLabel] | None = None

        self._root.update_idletasks()
        self._apply_window_styles()
        self._exclude_from_capture()

    # ------------------------------------------------------------------
    # Ventana
    # ------------------------------------------------------------------
    def _hwnd(self) -> int:
        return self._root.winfo_id()

    def _toplevel_hwnd(self) -> int:
        """Tk devuelve el HWND interno; las APIs de afinidad necesitan el de nivel superior."""
        inner = self._hwnd()
        parent = win32gui.GetParent(inner)
        return parent or inner

    def _apply_window_styles(self) -> None:
        hwnd = self._hwnd()
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE
        if CONFIG.click_through:
            style |= win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0, 0, 0), 0, win32con.LWA_COLORKEY)

    def _exclude_from_capture(self) -> None:
        """Hace que el overlay sea invisible para mss/OCR (evita leer nuestra propia traducción)."""
        try:
            func = ctypes.windll.user32.SetWindowDisplayAffinity
            func.argtypes = [wintypes.HWND, wintypes.DWORD]
            func.restype = wintypes.BOOL
            ok = func(self._toplevel_hwnd(), WDA_EXCLUDEFROMCAPTURE)
            if ok:
                LOGGER.info("Overlay excluido de la captura de pantalla")
            else:
                LOGGER.warning(
                    "No se pudo excluir el overlay de la captura (error=%s). "
                    "Requiere Windows 10 build 19041 o superior.",
                    win32api.GetLastError(),
                )
        except Exception:
            LOGGER.exception("Error al excluir el overlay de la captura")

    def _raise_above_apps(self) -> None:
        win32gui.SetWindowPos(
            self._hwnd(),
            win32con.HWND_TOPMOST,
            self._left,
            self._top,
            self._width,
            self._height,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )

    def show(self) -> None:
        if not self._visible:
            self._root.deiconify()
            self._visible = True
            self._root.update_idletasks()
            self._apply_window_styles()
            self._exclude_from_capture()
        self._raise_above_apps()

    def hide(self) -> None:
        if self._visible:
            self._root.withdraw()
            self._visible = False

    def clear(self) -> None:
        self._canvas.delete("all")

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def _draw_label(self, label: OverlayLabel) -> None:
        """Dibuja la traducción sobre un rectángulo sólido que tapa el texto original."""
        x = label.x - self._left
        y = label.y - self._top

        if x < -80 or y < -80 or x > self._width + 80 or y > self._height + 80:
            return

        pad = getattr(CONFIG, "overlay_bg_padding", 3)
        bg_color = getattr(CONFIG, "overlay_bg_color", "#1E293B")
        wrap_w = max(60, label.width + 8)

        # Tamaño de letra proporcional al texto original (en píxeles, por eso negativo).
        px = max(CONFIG.overlay_font_size, min(int(label.height * 0.75), 28))
        font = ("Segoe UI", -px)

        text_id = self._canvas.create_text(
            x,
            y,
            text=label.text,
            anchor="nw",
            fill=CONFIG.overlay_text_color,
            font=font,
            width=wrap_w,
        )

        bbox = self._canvas.bbox(text_id)
        if not bbox:
            return
        tx1, ty1, tx2, ty2 = bbox

        # El fondo cubre el texto original Y todo lo que ocupe la traducción.
        x1 = min(x, tx1) - pad
        y1 = min(y, ty1) - pad
        x2 = max(x + label.width, tx2) + pad
        y2 = max(y + label.height, ty2) + pad

        rect_id = self._canvas.create_rectangle(
            x1, y1, x2, y2, fill=bg_color, outline=""
        )
        self._canvas.tag_lower(rect_id, text_id)

    def _group_labels(self, blocks: list[TextBlock], translations: dict[str, str]) -> list[OverlayLabel]:
        """Une fragmentos de la misma línea, pero separa columnas distintas."""
        items: list[tuple[TextBlock, str]] = []
        for block in sorted(blocks, key=lambda b: (b.y, b.x)):
            translated = translations.get(block.text)
            if translated:
                items.append((block, translated))

        groups: list[list[tuple[TextBlock, str]]] = []
        for block, tr in items:
            center = block.y + block.height / 2
            placed = False
            for group in groups:
                ref = group[0][0]
                ref_center = ref.y + ref.height / 2
                if abs(center - ref_center) > max(6, ref.height * 0.5):
                    continue  # no está en la misma línea

                max_gap = max(30, int(block.height * 2))
                near = any(
                    block.x <= m.x + m.width + max_gap and block.x + block.width >= m.x - max_gap
                    for m, _ in group
                )
                if near:
                    group.append((block, tr))
                    placed = True
                    break
            if not placed:
                groups.append([(block, tr)])

        labels: list[OverlayLabel] = []
        for group in sorted(groups, key=lambda g: (min(b.y for b, _ in g), min(b.x for b, _ in g))):
            group.sort(key=lambda item: item[0].x)

            parts: list[str] = []
            for _, tr in group:
                if not parts or parts[-1] != tr:
                    parts.append(tr)

            left = min(b.x for b, _ in group)
            top = min(b.y for b, _ in group)
            right = max(b.x + b.width for b, _ in group)
            bottom = max(b.y + b.height for b, _ in group)

            labels.append(
                OverlayLabel(
                    x=left,
                    y=top,
                    text=" ".join(parts),
                    width=max(1, right - left),
                    height=max(1, bottom - top),
                )
            )
        return labels

    def render(self, labels: list[OverlayLabel]) -> None:
        visible = labels[: CONFIG.max_overlay_blocks]

        # Evita repintar (y parpadear) cuando el contenido no cambió.
        if self._last_labels is not None and visible == self._last_labels:
            return
        self._last_labels = visible

        self.clear()
        if not visible:
            if CONFIG.hide_when_empty:
                self.hide()
            return

        self.show()
        for label in visible:
            self._draw_label(label)

    def update_from_blocks(self, blocks: list[TextBlock], translations: dict[str, str]) -> None:
        self.render(self._group_labels(blocks, translations))

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def schedule(self, callback) -> None:
        self._root.after(CONFIG.ui_poll_ms, callback)

    def request_quit(self) -> None:
        self._root.after(0, self._root.quit)

    def run_mainloop(self) -> None:
        self._root.mainloop()

    def destroy(self) -> None:
        self._root.destroy()

    def raise_to_front(self) -> None:
        if self._visible:
            self._raise_above_apps()
