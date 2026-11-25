"""Typed API errors and the single error envelope used by every endpoint.

Error codes follow Docs/DataSchema.md section 7 where a matching code exists.
The dialogue endpoints add two transport-level codes of their own:
  - RATE_LIMITED (429)        local abuse protection, Retry-After is set.
  - INTERNAL_ERROR (500)      unexpected server fault, no internals leaked.
Model failures are *not* HTTP errors: they are successful turn results with a
`fallback_reason`, exactly like Docs/DataSchema.md section 5 requires.
"""

from __future__ import annotations

from typing import Any


class ErrorCodes:
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    TURN_BUSY = "TURN_BUSY"
    TURN_EXPIRED = "TURN_EXPIRED"
    LOCAL_AUTH_REQUIRED = "LOCAL_AUTH_REQUIRED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiError(Exception):
    """A failure that maps to the DataSchema error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


def invalid_request(message: str, *, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(400, ErrorCodes.INVALID_REQUEST, message, details=details)


def validation_error(message: str, *, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(422, ErrorCodes.VALIDATION_ERROR, message, details=details)


def not_found(message: str) -> ApiError:
    return ApiError(404, ErrorCodes.NOT_FOUND, message)


def precondition_failed(message: str, *, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(409, ErrorCodes.PRECONDITION_FAILED, message, details=details)


def turn_expired(message: str) -> ApiError:
    return ApiError(410, ErrorCodes.TURN_EXPIRED, message)


def turn_busy(message: str) -> ApiError:
    return ApiError(429, ErrorCodes.TURN_BUSY, message, retryable=True)
