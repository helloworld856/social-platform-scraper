from __future__ import annotations

import logging
import sys


LOGGER_ROOT = "crawler_tool"
_CONFIGURED = False


def setup_console_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    stream = sys.stdout or sys.stderr
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger(LOGGER_ROOT)
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_console_logging()
    if name.startswith(LOGGER_ROOT):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")
