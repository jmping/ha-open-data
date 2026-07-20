"""Shared HTTP helpers for Open Data providers."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponseError, ClientSession, ContentTypeError

from .base import OpenDataConnectionError, OpenDataResponseError

REQUEST_TIMEOUT = 15
USER_AGENT = "Home Assistant Open Data integration"


def normalize_portal_url(portal_url: str) -> str:
    """Normalize and validate a portal root URL."""
    value = portal_url.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Portal URL must contain a valid HTTP(S) hostname")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


class JsonClient:
    """Small async JSON client using Home Assistant's shared session."""

    def __init__(self, session: ClientSession, portal_url: str) -> None:
        self._session = session
        self.portal_url = normalize_portal_url(portal_url)

    async def async_get_json(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> Any:
        """Issue a GET and decode JSON with stable exceptions."""
        url = f"{self.portal_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    url, params=params, headers={"User-Agent": USER_AGENT}
                ) as response:
                    response.raise_for_status()
                    return await response.json(content_type=None)
        except ClientResponseError as err:
            raise OpenDataResponseError(
                f"Portal returned HTTP {err.status} for {url}"
            ) from err
        except (ContentTypeError, ValueError) as err:
            raise OpenDataResponseError(f"Portal returned invalid JSON for {url}") from err
        except (ClientError, TimeoutError) as err:
            raise OpenDataConnectionError(f"Unable to reach portal: {url}") from err
