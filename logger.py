"""Registro de actividad en archivo y consola."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "traductor.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("traductor")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


LOGGER = setup_logging()
