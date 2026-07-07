"""Registro de actividad en archivo."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "traductor.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("traductor")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(handler)
    return logger


LOGGER = setup_logging()
