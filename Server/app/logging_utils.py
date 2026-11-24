"""Log redaction.

Two independent rules govern secrets in this service:

1. a key is never put into a log record on purpose (see ``config.py`` and the
   providers, which only ever log provider ids and status codes);
2. this filter is the second line of defence, because an exception from a
   third-party library or a future edit must not be able to print a key.

It rewrites ``sk-…`` tokens, ``Bearer …`` credentials and ``api_key=…`` /
``token: …`` style assignments before the record reaches any handler.
"""

from __future__ import annotations

import logging
import re

_REDACTED = "[REDACTED]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{4,}"), "sk-" + _REDACTED),
    (re.compile(r"(?i)\b(bearer)(\s+)[A-Za-z0-9._\-]{8,}"), r"\1\2" + _REDACTED),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|authorization)"
            r"(\s*[=:]\s*)['\"]?(?!(?:bearer|\[REDACTED\])[^\s'\",;}\]]{0,})[^\s'\",;}\]]{4,}"
        ),
        r"\1\2" + _REDACTED,
    ),
)


def redact(text: str) -> str:
    """Return ``text`` with anything that looks like a credential removed."""

    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RedactingFilter(logging.Filter):
    """Rewrite formatted log messages so no credential reaches a handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # pragma: no cover - malformed format args
            rendered = str(record.msg)
        cleaned = redact(rendered)
        if cleaned != rendered:
            record.msg = cleaned
            record.args = ()
        return True


def install_log_redaction(*loggers: logging.Logger) -> None:
    redacting = RedactingFilter()
    for logger in loggers or (logging.getLogger(),):
        _attach(logger, redacting)
        for handler in logger.handlers:
            _attach(handler, redacting)


def _attach(target: logging.Logger | logging.Handler, redacting: RedactingFilter) -> None:
    if not any(isinstance(existing, RedactingFilter) for existing in target.filters):
        target.addFilter(redacting)
