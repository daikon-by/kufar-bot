from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from kufar_bot.config import settings

LOG_DIR = Path("data")
LOG_FILE = LOG_DIR / "kufar_bot.log"
CONSOLE_LOG = LOG_DIR / "console.log"


def _configure_stdio_utf8() -> None:
    """Windows console (cp1251) cannot print emoji in log lines without UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _file_log_renderer(
    logger: logging.Logger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> str:
    ts = event_dict.pop("timestamp", datetime.now().isoformat(timespec="seconds"))
    level = event_dict.pop("level", method_name)
    name = event_dict.pop("logger", logger.name)
    event = event_dict.pop("event", "")
    extras = " ".join(f"{k}={v!r}" for k, v in event_dict.items())
    line = f"{ts} [{level}] {name}: {event}"
    if extras:
        line = f"{line} {extras}"
    return line


def setup_logging() -> None:
    _configure_stdio_utf8()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(file_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    console.setFormatter(formatter)

    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=_file_log_renderer,
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    file_handler.setFormatter(file_formatter)

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
