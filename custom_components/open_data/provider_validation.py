"""Validate provider adapters before runtime use."""

from __future__ import annotations

from dataclasses import dataclass

from .provider_sdk import ProviderAdapter


@dataclass(frozen=True, slots=True)
class AdapterValidation:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_adapter(adapter: ProviderAdapter) -> AdapterValidation:
    """Return contract problems without invoking network operations."""
    errors: list[str] = []
    provider_id = getattr(adapter, "provider_id", "")
    if not isinstance(provider_id, str) or not provider_id.strip():
        errors.append("missing provider_id")
    if not callable(getattr(adapter, "discover", None)):
        errors.append("missing discover")
    if not callable(getattr(adapter, "describe_dataset", None)):
        errors.append("missing describe_dataset")
    if getattr(adapter, "capabilities", None) is None:
        errors.append("missing capabilities")
    return AdapterValidation(not errors, tuple(errors))
