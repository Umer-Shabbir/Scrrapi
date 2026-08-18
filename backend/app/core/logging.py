"""Structured logging (11.2).

Every log line emitted from the API, the Celery workers, and the scraping modules
carries the same machine-readable envelope, plus whatever job/target/place context
is bound at the time it was written:

    {"ts": "...", "level": "INFO", "logger": "app.workers.tasks",
     "msg": "place scraped", "service": "worker",
     "job_id": "...", "target_id": "...", "place_url": "..."}

Context is bound with `log_context(...)` (a context manager) rather than passed
down through every call signature, so a scraping helper five frames deep still
logs the job it belongs to. It's stored in a `ContextVar`, which means it's
correct per-task under Celery's prefork pool *and* per-request/per-coroutine
under asyncio -- a nested bind never leaks out of its `with` block.

Call `configure_logging()` once per process: `app.main` does it for the API,
the `setup_logging` Celery signal does it for workers (that signal also stops
Celery from installing its own handlers on top).
"""

import json
import logging
import logging.handlers
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings

# Fields every LogRecord carries by default. Anything *not* in here was passed by
# a caller as `logger.info(..., extra={...})`, so it belongs in the JSON output.
_RESERVED_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}

CONTEXT_FIELDS = ("job_id", "target_id", "place_url", "source", "keyword", "location")

# Default is None, not {}: a mutable default on a ContextVar is shared by every
# context that never set one, so an accidental in-place update would leak globally.
_log_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)

_configured = False


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Bind fields onto every log line emitted inside the block.

    Nests: an inner bind sees the outer one's fields and adds to them, and the
    outer values are restored on exit. `None` values are dropped so callers can
    pass optional context unconditionally.
    """
    merged = {**get_log_context(), **{k: v for k, v in fields.items() if v is not None}}
    token = _log_context.set(merged)
    try:
        yield
    finally:
        _log_context.reset(token)


def get_log_context() -> dict[str, Any]:
    return dict(_log_context.get() or {})


class ContextFilter(logging.Filter):
    """Copies the bound context onto the record so both formatters can see it."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in get_log_context().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: fixed envelope + bound context + `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable local-dev form: the standard line plus `key=value` context."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        context = " ".join(
            f"{key}={getattr(record, key)}" for key in CONTEXT_FIELDS if hasattr(record, key)
        )
        return f"{line} [{context}]" if context else line


def configure_logging(service: str = "api", *, force: bool = False) -> None:
    """Install the structured handler on the root logger. Idempotent per process."""
    global _configured
    if _configured and not force:
        return

    settings = get_settings()
    formatter: logging.Formatter = (
        JsonFormatter() if settings.log_format.lower() == "json" else TextFormatter()
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ContextFilter())
    console_handler.addFilter(_ServiceFilter(service))
    console_handler.setLevel((settings.console_log_level or settings.log_level).upper())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(console_handler)

    # Full record, always JSON regardless of log_format, so a text-console dev
    # run still leaves a machine-readable file behind. Rotated so a long-lived
    # dev/worker process doesn't grow this file without bound.
    if settings.log_file:
        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file, maxBytes=20_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(ContextFilter())
        file_handler.addFilter(_ServiceFilter(service))
        root.addHandler(file_handler)

    root.setLevel(settings.log_level.upper())

    # uvicorn installs its own handlers at import time; drop them so access/error
    # lines go through this formatter instead of being emitted twice in two shapes.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # At LOG_LEVEL=INFO (the default) these libraries log one line per outbound
    # HTTP request/DB query -- fine at the old worker concurrency (2-4), but at
    # MAX_CONCURRENT_TARGETS (64) it's dozens of interleaved lines a second and
    # was enough console volume to crash a terminal (see the 08:35 log this
    # comment was added over). Raised to WARNING so a *failing* request/query
    # still surfaces; only the routine per-call noise is dropped. This only
    # affects the console handler above -- it doesn't touch our own app.* and
    # celery.* loggers, whose INFO lines (job/target/place lifecycle) are the
    # actual signal this app's logs exist for.
    for name in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self.service
        return True
