"""Structured logging with structlog.

In dev, logs are coloured, human-readable lines. In prod, each log line is one JSON object,
which log tools can search by field (e.g. every line with `request_id=abc`). Standard-library
loggers (uvicorn, httpx) go through the same pipeline, so all output looks consistent.
"""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog and the standard `logging` module once at startup."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # adds request_id etc. bound per request
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    # The dev ConsoleRenderer prints exceptions itself; JSON needs them turned into a string field.
    render_chain: list[structlog.types.Processor] = (
        [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        if json_logs
        else [structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())]
    )

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *render_chain],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # HTTP client libraries log every request at INFO, which is noise for health checks.
    # (httpx2 is the HTTP client used by the OpenAI SDK.)
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
