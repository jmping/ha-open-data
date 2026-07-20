"""Deterministic registry for provider adapter implementations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .provider_sdk import ProviderAdapter


@dataclass(slots=True)
class ProviderRegistry:
    """Store adapters by stable provider identifier."""

    _adapters: dict[str, ProviderAdapter] = field(default_factory=dict)

    def register(self, adapter: ProviderAdapter) -> None:
        provider_id = adapter.provider_id.strip().casefold()
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        if provider_id in self._adapters:
            raise ValueError(f"provider already registered: {provider_id}")
        self._adapters[provider_id] = adapter

    def get(self, provider_id: str) -> ProviderAdapter:
        key = provider_id.strip().casefold()
        try:
            return self._adapters[key]
        except KeyError as err:
            raise KeyError(f"unknown provider: {provider_id}") from err

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
