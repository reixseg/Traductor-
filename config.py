"""Configuración del traductor en vivo."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    capture_interval: float = 0.35
    min_sleep_after_cycle: float = 0.1
    ocr_max_width: int = 1200
    ocr_startup_delay: float = 0.5
    ocr_confidence: float = 0.45

    content_top_margin: int = 90
    content_bottom_margin: int = 50
    content_left_margin: int = 40

    source_lang: str = "auto"
    target_lang: str = "es"
    translate_batch_size: int = 20
    skip_unchanged_screen: bool = True

    max_lines_per_cycle: int = 16
    min_line_length: int = 6
    min_text_length: int = 3

    overlay_font_size: int = 12
    panel_font_size: int = 11
    overlay_text_color: str = "#FFF8E1"
    overlay_outline_color: str = "#0F172A"
    overlay_bg_color: str = "#1E293B"
    overlay_bg_padding: int = 3
    overlay_max_width: int = 520
    max_overlay_blocks: int = 20
    overlay_line_group_px: int = 14
    click_through: bool = True
    hide_when_empty: bool = True

    raise_interval_sec: float = 1.5
    show_startup_notice: bool = True
    ui_poll_ms: int = 60
    auto_restart_on_error: bool = True
    capture_region: dict[str, int] | None = None

    # Traducción offline (Argos Translate)
    argos_source_languages: list[str] = field(default_factory=lambda: ["en"])
    argos_auto_install: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppConfig":
        if not data:
            return cls()

        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CONFIG = AppConfig()


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or CONFIG_PATH)
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                return AppConfig.from_dict(json.load(handle))
        except Exception:
            pass

    save_config(CONFIG, config_path)
    return CONFIG


def save_config(config: AppConfig | None = None, path: str | Path | None = None) -> None:
    target = Path(path or CONFIG_PATH)
    payload = (config or CONFIG).to_dict()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_config(overrides: dict[str, Any], path: str | Path | None = None) -> AppConfig:
    for key, value in overrides.items():
        setattr(CONFIG, key, value)
    save_config(CONFIG, path)
    return CONFIG


CONFIG = load_config()
