import logging
import re
import structlog
from app.config import settings

SENSITIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{16}\b"), "***CARD***"),
    (re.compile(r"\$\s*\d+(?:\.\d{2})?"), "***AMOUNT***"),
    (
        re.compile(r"(?i)(token|secret|password|apikey|api_key)[=:]\s*\S+"),
        r"\1=***REDACTED***",
    ),
]


def _redact_processor(_logger, _method_name, event_dict):
    event = event_dict.get("event")
    if isinstance(event, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            event = pattern.sub(replacement, event)
        event_dict["event"] = event
    for key in list(event_dict.keys()):
        if any(p in key.lower() for p in ["token", "secret", "password", "key"]):
            event_dict[key] = "***REDACTED***"
    return event_dict


def setup_logging() -> None:
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.DEBUG:
        processors = shared + [structlog.dev.ConsoleRenderer()]
    else:
        processors = shared + [_redact_processor, structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
