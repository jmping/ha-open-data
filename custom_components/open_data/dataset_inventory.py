"""Persistent, entity-independent source and dataset inventory.

This registry stores bounded metadata and prepared activation payloads. A source or
dataset can remain in the inventory without a Home Assistant config entry, and
existing config entries remain the authority for active runtime entities.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
)

DATA_INVENTORY = "dataset_inventory"
_STORAGE_VERSION = 1
_STORAGE_KEY = "open_data.dataset_inventory"
_MAX_SOURCES = 100
_MAX_DATASETS = 2000
_MAX_PAYLOAD_BYTES = 128_000
_MAX_TOTAL_BYTES = 8_000_000
_MAX_LABEL = 512


def _now() -> str:
    return datetime.now(UTC).isoformat()


def source_key(provider: str, portal_url: str) -> str:
    """Produce a stable key for simple URL aliases of one source."""
    parts = urlsplit(portal_url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("An inventory source requires an HTTP(S) portal URL")
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (
        parts.scheme.lower() == "https" and port == 443
    )):
        hostname = f"{hostname}:{port}"
    return f"{provider.casefold()}:{urlunsplit((parts.scheme.lower(), hostname, parts.path.rstrip('/'), '', ''))}"


def dataset_key(source_id: str, dataset_id: str, resource_id: str | None) -> str:
    """Distinguish resources without collapsing siblings under a portal."""
    if not dataset_id.strip():
        raise ValueError("A dataset identifier is required")
    return json.dumps([source_id, dataset_id, resource_id or ""], separators=(",", ":"))


@dataclass(slots=True)
class InventorySource:
    key: str
    provider: str
    portal_url: str
    created_at: str
    updated_at: str
    status: str = "discovered"
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "provider": self.provider,
            "portal_url": self.portal_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "error": self.error,
        }


@dataclass(slots=True)
class InventoryDataset:
    key: str
    source_key: str
    dataset_id: str
    resource_id: str | None
    title: str
    created_at: str
    updated_at: str
    status: str = "discovered"
    error: str | None = None
    prepared: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_key": self.source_key,
            "dataset_id": self.dataset_id,
            "resource_id": self.resource_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "error": self.error,
            "prepared": deepcopy(self.prepared),
        }


class DatasetInventory:
    """Durably track sources and datasets, independently of entity creation."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY
        )
        self._sources: dict[str, InventorySource] = {}
        self._datasets: dict[str, InventoryDataset] = {}
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Restore stored metadata; never create or activate entries on load."""
        stored = await self._store.async_load() or {}
        async with self._lock:
            self._sources = {}
            for item in stored.get("sources", [])[:_MAX_SOURCES]:
                if not isinstance(item, dict):
                    continue
                try:
                    key = source_key(str(item["provider"]), str(item["portal_url"]))
                    self._sources[key] = InventorySource(
                        key, str(item["provider"]), str(item["portal_url"]),
                        str(item.get("created_at", "")), str(item.get("updated_at", "")),
                        str(item.get("status", "discovered")), item.get("error"),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            self._datasets = {}
            for item in stored.get("datasets", [])[:_MAX_DATASETS]:
                if not isinstance(item, dict):
                    continue
                try:
                    sid = str(item["source_key"])
                    if sid not in self._sources:
                        continue
                    did = str(item["dataset_id"])
                    resource = item.get("resource_id")
                    key = dataset_key(sid, did, resource)
                    prepared = item.get("prepared")
                    if prepared is not None and not _bounded_payload(prepared):
                        prepared = None
                    self._datasets[key] = InventoryDataset(
                        key, sid, did, resource, str(item.get("title", did))[:_MAX_LABEL],
                        str(item.get("created_at", "")), str(item.get("updated_at", "")),
                        str(item.get("status", "discovered")), item.get("error"),
                        deepcopy(prepared),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

    def sources(self) -> tuple[InventorySource, ...]:
        return tuple(deepcopy(item) for item in self._sources.values())

    def datasets(self, source_id: str | None = None) -> tuple[InventoryDataset, ...]:
        return tuple(
            deepcopy(item) for item in self._datasets.values()
            if source_id is None or item.source_key == source_id
        )

    def get_dataset(
        self, provider: str, portal_url: str, dataset_id: str,
        resource_id: str | None = None,
    ) -> InventoryDataset | None:
        key = dataset_key(source_key(provider, portal_url), dataset_id, resource_id)
        value = self._datasets.get(key)
        return deepcopy(value) if value is not None else None

    async def async_register_source(
        self, provider: str, portal_url: str, *, status: str = "discovered",
        error: str | None = None,
    ) -> InventorySource:
        """Upsert a canonical source while preserving its original registration."""
        key = source_key(provider, portal_url)
        async with self._lock:
            old = self._sources.get(key)
            if old is None and len(self._sources) >= _MAX_SOURCES:
                raise ValueError("Source inventory limit reached")
            now = _now()
            source = InventorySource(
                key, provider, portal_url, old.created_at if old else now,
                now, status, error,
            )
            self._sources[key] = source
            try:
                await self._async_save()
            except Exception:
                if old is None:
                    self._sources.pop(key, None)
                else:
                    self._sources[key] = old
                raise
            return deepcopy(source)

    async def async_register_dataset(
        self, provider: str, portal_url: str, dataset_id: str,
        resource_id: str | None, title: str, *,
        status: str = "discovered", error: str | None = None,
        prepared: dict[str, Any] | None = None,
    ) -> InventoryDataset:
        """Upsert metadata while retaining a previously prepared payload.

        Preparation failures never remove the last successful snapshot.
        """
        key_source = source_key(provider, portal_url)
        key = dataset_key(key_source, dataset_id, resource_id)
        if prepared is not None and not _bounded_payload(prepared):
            raise ValueError("Prepared dataset payload exceeds safe storage bounds")
        async with self._lock:
            created_source = key_source not in self._sources
            if created_source:
                if len(self._sources) >= _MAX_SOURCES:
                    raise ValueError("Source inventory limit reached")
                now = _now()
                self._sources[key_source] = InventorySource(
                    key_source, provider, portal_url, now, now
                )
            old = self._datasets.get(key)
            if old is None and len(self._datasets) >= _MAX_DATASETS:
                if created_source:
                    self._sources.pop(key_source, None)
                raise ValueError("Dataset inventory limit reached")
            now = _now()
            dataset = InventoryDataset(
                key, key_source, dataset_id, resource_id,
                title[:_MAX_LABEL], old.created_at if old else now, now,
                status, error,
                deepcopy(prepared) if prepared is not None else (
                    deepcopy(old.prepared) if old else None
                ),
            )
            self._datasets[key] = dataset
            try:
                await self._async_save()
            except Exception:
                if old is None:
                    self._datasets.pop(key, None)
                else:
                    self._datasets[key] = old
                if created_source:
                    self._sources.pop(key_source, None)
                raise
            return deepcopy(dataset)

    async def async_save_prepared(self, entry: dict[str, Any]) -> InventoryDataset:
        """Persist a bounded inference snapshot without activating entities."""
        data = entry["data"]
        return await self.async_register_dataset(
            str(data[CONF_PROVIDER]), str(data[CONF_PORTAL_URL]),
            str(data[CONF_DATASET_ID]), data.get(CONF_RESOURCE_ID),
            str(entry["title"]), status="ready", prepared=entry,
        )

    async def async_mark_activated(self, entry: dict[str, Any]) -> None:
        """Record the accepted activation request.

        Actual runtime activity is determined by the HA config-entry lifecycle.
        """
        data = entry["data"]
        await self.async_register_dataset(
            str(data[CONF_PROVIDER]), str(data[CONF_PORTAL_URL]),
            str(data[CONF_DATASET_ID]), data.get(CONF_RESOURCE_ID),
            str(entry["title"]), status="activation_requested",
        )

    async def _async_save(self) -> None:
        payload = {
            "sources": [item.as_dict() for item in self._sources.values()],
            "datasets": [item.as_dict() for item in self._datasets.values()],
        }
        encoded = json.dumps(payload, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > _MAX_TOTAL_BYTES:
            raise ValueError("Open Data inventory storage limit reached")
        await self._store.async_save(payload)


def _bounded_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        return len(json.dumps(
            value, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")) <= _MAX_PAYLOAD_BYTES
    except (TypeError, ValueError):
        return False
