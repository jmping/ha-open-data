"""Privacy-preserving feedback helpers for portal discovery reports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_STORAGE_VERSION = 1
_STORAGE_KEY = f"{DOMAIN}.feedback"


@dataclass(frozen=True, slots=True)
class FeedbackReport:
    """Metadata-only portal report suitable for optional central submission."""

    installation_id: str
    portal_id: str
    metadata_hash: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return the wire representation."""
        return {
            "installation_id": self.installation_id,
            "portal_id": self.portal_id,
            "metadata_hash": self.metadata_hash,
            "payload": self.payload,
        }


class FeedbackRegistry:
    """Persist one anonymous installation identity and per-portal report hashes."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, _STORAGE_VERSION, _STORAGE_KEY)
        self._installation_id = ""
        self._last_report_hashes: dict[str, str] = {}

    @property
    def installation_id(self) -> str:
        """Return the random, stable identifier for this installation."""
        return self._installation_id

    async def async_load(self) -> None:
        """Load state, creating an anonymous identifier when needed."""
        data = await self._store.async_load() or {}
        self._installation_id = str(data.get("installation_id") or uuid4())
        hashes = data.get("last_report_hashes") or {}
        self._last_report_hashes = {str(key): str(value) for key, value in hashes.items()}
        await self._save()

    def build_report(self, portal_id: str, payload: Mapping[str, Any]) -> FeedbackReport | None:
        """Build a report only when this installation has new metadata for a portal."""
        normalized_payload = _normalize(payload)
        metadata_hash = _metadata_hash(normalized_payload)
        if self._last_report_hashes.get(portal_id) == metadata_hash:
            return None
        return FeedbackReport(
            installation_id=self._installation_id,
            portal_id=portal_id,
            metadata_hash=metadata_hash,
            payload=normalized_payload,
        )

    async def async_mark_submitted(self, report: FeedbackReport) -> None:
        """Record a successfully submitted report for local duplicate suppression."""
        self._last_report_hashes[report.portal_id] = report.metadata_hash
        await self._save()

    async def _save(self) -> None:
        await self._store.async_save(
            {
                "installation_id": self._installation_id,
                "last_report_hashes": self._last_report_hashes,
            }
        )


def _normalize(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize metadata into a stable JSON-compatible structure."""
    return json.loads(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")))


def _metadata_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()
