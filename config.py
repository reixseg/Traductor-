"""Configuración del traductor en vivo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    capture_interval: float = 0.35
    min_sleep_after_cycle: float = 0.1
    ocr_max_width: int = 1200
    ocr_startup_delay: float = 0.5
    ocr_confidence: float = 0.45

    content_top_margin: int = 90
    content_bottom_margin: int = 50
    content_left_margin: int = 40

    target_lang: str = "es"
    translate_batch_size: int = 20
    skip_unchanged_screen: bool = True

    max_lines_per_cycle: int = 16
    min_line_length: int = 6
    min_text_length: int = 3

    # Overlay estilo subtítulo (sin cajas blancas)
    overlay_font_size: int = 12
    overlay_text_color: str = "#FFF8E1"
    overlay_outline_color: str = "#0F172A"
    overlay_max_width: int = 520
    max_overlay_blocks: int = 20
    overlay_line_group_px: int = 14
    click_through: bool = True
    hide_when_empty: bool = True

    raise_interval_sec: float = 1.5
    show_startup_notice: bool = True
    ui_poll_ms: int = 60


CONFIG = AppConfig()
