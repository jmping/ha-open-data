"""Structured diagnostics for config-flow failures."""

from __future__ import annotations

import logging
import platform
from collections.abc import Mapping
from importlib import import_module
from typing import Any

from .const import DOMAIN

LOGGER = logging.getLogger(__package__)

_REDACTED_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
}


def _home_assistant_version() -> str:
    """Return the Home Assistant version without requiring HA in fast tests."""
    try:
        const = import_module("homeassistant.const")
    except ModuleNotFoundError:
        return "unavailable"
    return str(getattr(const, "__version__", "unknown"))


def _safe_value(value: Any) -> Any:
    """Return a bounded, log-safe representation."""
    if isinstance(value, Mapping):
        return {
            str(key): "<redacted>"
            if str(key).lower() in _REDACTED_KEYS
            else _safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item) for item in list(value)[:20]]
    if isinstance(value, str):
        return value[:500]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)[:500]


def log_flow_breadcrumb(step: str, message: str, **context: Any) -> None:
    """Record one concise config-flow breadcrumb at INFO level."""
    LOGGER.info(
        "Open Data config flow [%s]: %s | context=%s",
        step,
        message,
        _safe_value(context),
    )


def log_flow_exception(
    step: str,
    exc: BaseException,
    *,
    integration_version: str,
    **context: Any,
) -> None:
    """Log a serious, structured config-flow failure with traceback."""
    LOGGER.exception(
        "Open Data config flow failed\n"
        "========== Open Data Diagnostics ==========\n"
        "domain=%s\n"
        "integration_version=%s\n"
        "home_assistant_version=%s\n"
        "python_version=%s\n"
        "flow_step=%s\n"
        "exception_type=%s\n"
        "exception=%s\n"
        "context=%s\n"
        "===========================================",
        DOMAIN,
        integration_version,
        _home_assistant_version(),
        platform.python_version(),
        step,
        type(exc).__name__,
        exc,
        _safe_value(context),
    )
