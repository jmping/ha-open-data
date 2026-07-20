"""Structured provider SDK failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderErrorKind(StrEnum):
    AUTHENTICATION = "authentication"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """Serializable provider failure suitable for diagnostics."""

    provider_id: str
    kind: ProviderErrorKind
    message: str
    retryable: bool = False


class ProviderError(RuntimeError):
    """Exception carrying a normalized provider failure."""

    def __init__(self, failure: ProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure
