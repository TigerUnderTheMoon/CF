"""Structured logging configuration for FMA.

Supports two output formats controlled by the ``FMA_LOG_FORMAT`` environment
variable:

- ``console`` (default): human-readable, colourised output for development.
- ``json``: machine-parseable JSON lines for production log aggregation.

When ``structlog`` is not installed the module silently falls back to the
standard-library ``logging`` module so that logging calls never raise
``ImportError``.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

_LOG_FORMAT = os.environ.get("FMA_LOG_FORMAT", "console").lower()
_CONFIGURED = False
_STRUCTLOG_AVAILABLE = False

try:
    import structlog as _structlog
    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _structlog = None  # type: ignore[assignment]


class _FallbackLogger:
    """Minimal structlog-compatible wrapper around stdlib logging."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kw: Any) -> None:
        if kw:
            extra = ", ".join(f"{k}={v!r}" for k, v in kw.items())
            self._logger.log(level, "%s %s", event, extra)
        else:
            self._logger.log(level, "%s", event)

    def debug(self, event: str, **kw: Any) -> None:
        self._log(logging.DEBUG, event, **kw)

    def info(self, event: str, **kw: Any) -> None:
        self._log(logging.INFO, event, **kw)

    def warning(self, event: str, **kw: Any) -> None:
        self._log(logging.WARNING, event, **kw)

    def error(self, event: str, **kw: Any) -> None:
        self._log(logging.ERROR, event, **kw)

    def critical(self, event: str, **kw: Any) -> None:
        self._log(logging.CRITICAL, event, **kw)

    def log(self, level: int, event: str, **kw: Any) -> None:
        self._log(level, event, **kw)

    def bind(self, **kw: Any) -> "_FallbackLogger":
        return self


def configure_logging(
    *,
    log_level: str = "INFO",
    log_format: str | None = None,
    force: bool = False,
) -> Any:
    """Configure structlog (or fallback logging) for the FMA package.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Override ``FMA_LOG_FORMAT`` (``"console"`` or ``"json"``).
        force: Re-configure even if already configured.

    Returns:
        A structlog-bound logger factory, or a stdlib ``logging.Logger``
        when structlog is not installed.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return get_logger

    fmt = (log_format or _LOG_FORMAT).lower()
    if fmt not in {"console", "json"}:
        fmt = "console"

    level = getattr(logging, log_level.upper(), logging.INFO)

    if not _STRUCTLOG_AVAILABLE:
        _configure_fallback(level)
        _CONFIGURED = True
        return get_logger

    if fmt == "json":
        _configure_structlog_json(level)
    else:
        _configure_structlog_console(level)

    _CONFIGURED = True
    return get_logger


def get_logger(*args: Any, **initial_values: Any) -> Any:
    """Return a logger instance.  Works before and after configuration."""
    if not _CONFIGURED:
        configure_logging()

    name = args[0] if args else "fma"

    if not _STRUCTLOG_AVAILABLE:
        return _FallbackLogger(name)

    return _structlog.get_logger(*args, **initial_values)


def _configure_structlog_console(level: int) -> None:
    """Set up colourised, human-readable console output."""
    assert _structlog is not None

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    shared_processors: list[Any] = [
        _structlog.contextvars.merge_contextvars,
        _structlog.processors.add_log_level,
        _structlog.processors.StackInfoRenderer(),
        _structlog.dev.set_exc_info,
        _structlog.processors.TimeStamper(
            fmt="%Y-%m-%dT%H:%M:%S.%f", utc=True
        ),
    ]

    _structlog.configure(
        processors=shared_processors
        + [
            _structlog.dev.ConsoleRenderer(
                colors=sys.stderr.isatty()
            ),
        ],
        wrapper_class=_structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=_structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_structlog_json(level: int) -> None:
    """Set up JSON-lines output for production log aggregation."""
    assert _structlog is not None

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    shared_processors: list[Any] = [
        _structlog.contextvars.merge_contextvars,
        _structlog.processors.add_log_level,
        _structlog.processors.StackInfoRenderer(),
        _structlog.processors.format_exc_info,
        _structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    _structlog.configure(
        processors=shared_processors
        + [
            _structlog.processors.JSONRenderer(),
        ],
        wrapper_class=_structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=_structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_fallback(level: int) -> None:
    """Configure stdlib logging when structlog is not available."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger("fma")
    if not root.handlers:
        root.addHandler(handler)
        root.setLevel(level)
