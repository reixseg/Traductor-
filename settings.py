"""Ventana de configuración sencilla para el traductor."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import CONFIG, apply_config
from logger import LOGGER


class SettingsWindow:
    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("Configuración del traductor")
        self._root.geometry("480x420")
        self._root.resizable(False, False)

        tk.Label(
            self._root,
            text="Ajustes rápidos",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
            padx=16,
            pady=12,
        ).pack(fill="x")

        frame = ttk.Frame(self._root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Idioma origen:").grid(row=0, column=0, sticky="w", pady=4)
        self._source_lang = ttk.Entry(frame, width=20)
        self._source_lang.insert(0, CONFIG.source_lang)
        self._source_lang.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Idioma destino:").grid(row=1, column=0, sticky="w", pady=4)
        self._target_lang = ttk.Entry(frame, width=20)
        self._target_lang.insert(0, CONFIG.target_lang)
        self._target_lang.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Intervalo de captura (s):").grid(row=2, column=0, sticky="w", pady=4)
        self._capture_interval = ttk.Entry(frame, width=20)
        self._capture_interval.insert(0, str(CONFIG.capture_interval))
        self._capture_interval.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Confianza OCR:").grid(row=3, column=0, sticky="w", pady=4)
        self._ocr_confidence = ttk.Entry(frame, width=20)
        self._ocr_confidence.insert(0, str(CONFIG.ocr_confidence))
        self._ocr_confidence.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Mostrar aviso al iniciar:").grid(row=4, column=0, sticky="w", pady=4)
        self._show_notice = tk.BooleanVar(value=CONFIG.show_startup_notice)
        ttk.Checkbutton(frame, variable=self._show_notice).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Click-through:").grid(row=5, column=0, sticky="w", pady=4)
        self._click_through = tk.BooleanVar(value=CONFIG.click_through)
        ttk.Checkbutton(frame, variable=self._click_through).grid(row=5, column=1, sticky="w", pady=4)

        ttk.Button(frame, text="Guardar", command=self._save).grid(row=6, column=0, pady=16)
        ttk.Button(frame, text="Cerrar", command=self._root.destroy).grid(row=6, column=1, pady=16)

    def _save(self) -> None:
        try:
            overrides = {
                "source_lang": self._source_lang.get().strip() or "auto",
                "target_lang": self._target_lang.get().strip() or "es",
                "capture_interval": float(self._capture_interval.get().strip() or 0.35),
                "ocr_confidence": float(self._ocr_confidence.get().strip() or 0.45),
                "show_startup_notice": bool(self._show_notice.get()),
                "click_through": bool(self._click_through.get()),
            }
            apply_config(overrides)
            LOGGER.info("Configuración guardada desde la ventana")
        except Exception as exc:
            LOGGER.exception("Error al guardar configuración: %s", exc)
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()
