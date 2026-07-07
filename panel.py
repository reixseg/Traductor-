"""Ventana principal del traductor — visible y fácil de encontrar."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

import win32con
import win32gui

from config import CONFIG


class TranslationPanel:
    """Ventana normal con barra de título (aparece en la barra de tareas)."""

    def __init__(self, panel_left: int, panel_top: int, width: int, height: int) -> None:
        self._root = tk.Tk()
        self._root.title("Traductor EN → ES")
        self._root.configure(bg="#FFFFFF")
        self._root.geometry(f"{width}x{height}+{panel_left}+{panel_top}")
        self._root.minsize(320, 400)
        self._root.attributes("-topmost", True)

        # Borde naranja llamativo para que no se pierda sobre fondo negro del PDF.
        frame = tk.Frame(
            self._root,
            bg="#FFFFFF",
            highlightthickness=4,
            highlightbackground="#F97316",
            highlightcolor="#F97316",
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        header = tk.Frame(frame, bg="#2563EB", height=42)
        header.pack(fill="x")
        header.pack_propagate(False)

        self._title = tk.Label(
            header,
            text="Traducción al español",
            bg="#2563EB",
            fg="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            padx=12,
        )
        self._title.pack(fill="both", expand=True)

        self._body = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            font=("Segoe UI", CONFIG.panel_font_size),
            relief=tk.FLAT,
            padx=14,
            pady=12,
            state=tk.DISABLED,
        )
        self._body.pack(fill="both", expand=True)

        hint = tk.Label(
            frame,
            text="Ventana siempre visible · Cierra con la X o clic derecho en el icono de la bandeja",
            bg="#EFF6FF",
            fg="#1D4ED8",
            font=("Segoe UI", 9),
            anchor="w",
            padx=12,
            pady=8,
        )
        hint.pack(fill="x", side="bottom")

        self._root.protocol("WM_DELETE_WINDOW", self._hide_instead_of_close)
        self._root.update_idletasks()
        self._raise_panel()

    def _hide_instead_of_close(self) -> None:
        """Minimizar en lugar de cerrar (el cierre real es desde la bandeja)."""
        self._root.iconify()

    def _hwnd(self) -> int:
        return self._root.winfo_id()

    def _raise_panel(self) -> None:
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.attributes("-topmost", True)
            hwnd = self._hwnd()
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE
                | win32con.SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def set_status(self, message: str) -> None:
        self._title.config(text=message)
        self._raise_panel()

    def show_translations(self, translations: list[str]) -> None:
        self._body.config(state=tk.NORMAL)
        self._body.delete("1.0", tk.END)

        if not translations:
            self._body.insert(
                tk.END,
                "Esperando texto en inglés en pantalla...\n\n"
                "Consejo: no uses el PDF en pantalla completa.\n"
                "Deja visible esta ventana blanca a un lado del documento.\n",
            )
        else:
            for index, text in enumerate(translations, start=1):
                self._body.insert(tk.END, f"{index}. {text}\n\n")

        self._body.config(state=tk.DISABLED)
        self._body.yview_moveto(0.0)
        self.set_status(f"Traducción al español — {len(translations)} línea(s)")

    def schedule(self, callback) -> None:
        from config import CONFIG

        self._root.after(CONFIG.ui_poll_ms, callback)

    def request_quit(self) -> None:
        self._root.after(0, self._root.quit)

    def run_mainloop(self) -> None:
        self._root.mainloop()

    def destroy(self) -> None:
        self._root.destroy()
