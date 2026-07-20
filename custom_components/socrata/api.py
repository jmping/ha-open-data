"""Minimal asynchronous client for Socrata APIs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponseError, ClientSession

_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)
_FIELD_NAME_PATTERN = re.compile(r"^:?[a-zA-Z_][a-zA-Z0-9_]*$")
_USER_AGENT = "Home Assistant Socrata Open Data integration"


class SocrataError(Exception):
    """Base exception for Socrata client errors."""


class SocrataConnectionError(SocrataError):
    """Raised when the portal cannot be reached."""


class SocrataResponseError(SocrataError):
    """Raised when the portal returns an invalid or unexpected response."""


@dataclass(slots=True, frozen=True)
class SocrataDatasetMetadata:
    """Small normalized subset of Socrata dataset metadata."""

    dataset_id: str
    name: str
    description: str | None
    raw: dict[str, Any]


def normalize_portal_url(portal_url: str) -> str:
    """Normalize and validate a Socrata portal base URL."""
    value = portal_url.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Portal URL must contain a valid HTTP(S) hostname")

    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Portal URL must be a portal root URL")

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def validate_dataset_id(dataset_id: str) -> str:
    """Validate and normalize a Socrata four-by-four dataset identifier."""
    normalized = dataset_id.strip().lower()
    if not _DATASET_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Dataset ID must use Socrata's four-by-four format")
    return normalized


def validate_field_name(field_name: str) -> str:
    """Validate a column identifier used in a generated SoQL order clause."""
    normalized = field_name.strip()
    if not _FIELD_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Timestamp field is not a valid Socrata field identifier")
    return normalized


class SocrataClient:
    """Small async Socrata client using Home Assistant's shared session."""

    def __init__(self, session: ClientSession, portal_url: str) -> None:
        """Initialize the client."""
        self._session = session
        self.portal_url = normalize_portal_url(portal_url)

    async def async_get_dataset_metadata(
        self, dataset_id: str
    ) -> SocrataDatasetMetadata:
        """Fetch metadata for one dataset."""
        dataset_id = validate_dataset_id(dataset_id)
        url = f"{self.portal_url}/api/views/{dataset_id}"
        payload = await self._async_get_json(url)
        if not isinstance(payload, dict):
            raise SocrataResponseError("Dataset metadata was not a JSON object")

        name = payload.get("name")
        if not isinstance(name, str) or not name:
            raise SocrataResponseError("Dataset metadata did not include a name")

        description = payload.get("description")
        return SocrataDatasetMetadata(
            dataset_id=dataset_id,
            name=name,
            description=description if isinstance(description, str) else None,
            raw=payload,
        )

    async def async_query(
        self,
        dataset_id: str,
        *,
        select: str | None = None,
        where: str | None = None,
        order: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a SODA query and return JSON rows."""
        dataset_id = validate_dataset_id(dataset_id)
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        params: dict[str, str] = {"$limit": str(limit)}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order

        url = f"{self.portal_url}/resource/{dataset_id}.json"
        payload = await self._async_get_json(url, params=params)
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise SocrataResponseError("Dataset query did not return a list of rows")
        return payload

    async def async_latest_row(
        self, dataset_id: str, timestamp_field: str
    ) -> dict[str, Any] | None:
        """Return the newest row according to a selected timestamp field."""
        timestamp_field = validate_field_name(timestamp_field)
        rows = await self.async_query(
            dataset_id,
            order=f"{timestamp_field} DESC",
            limit=1,
        )
        return rows[0] if rows else None

    async def _async_get_json(
        self, url: str, *, params: dict[str, str] | None = None
    ) -> Any:
        """Issue a GET request and decode JSON with stable exceptions."""
        try:
            async with self._session.get(
                url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except ClientResponseError as err:
            raise SocrataResponseError(
                f"Socrata returned HTTP {err.status} for {url}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise SocrataConnectionError(f"Unable to reach Socrata portal: {url}") from err
        except ValueError as err:
            raise SocrataResponseError(f"Socrata returned invalid JSON for {url}") from err
