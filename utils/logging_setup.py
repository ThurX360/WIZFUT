"""Utility helpers for configuring application logging."""
from __future__ import annotations

import logging
import os
from typing import Optional

_LOG_FORMAT = "%(asctime)s | %(levelname)8s | %(message)s"


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """Configure and return a logger instance.

    The function is intentionally lightweight: when called multiple times it
    will reuse the same logger while avoiding duplicate handlers.  The log
    level can be controlled via the ``LOG_LEVEL`` environment variable
    (defaults to ``INFO``).
    """

    logger = logging.getLogger(name or "fc26-market")
    if logger.handlers:
        return logger

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
