"""Regression coverage for canonical provider API redirects."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from custom_components.open_data.providers.common import JsonClient
from custom_components.open_data.providers.redirecting_json import (
    install_redirecting_json_client,
)


class _Content:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode()

    async def iter_chunked(self, size: int):
        yield self._body


class _Response:
    def __init__(
        self,
        url: str,
        *,
        status: int,
        payload: object | None = None,
        location: str | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.headers = {"Location": location} if location else {}
        self.content = _Content(payload)
        self.content_length = None
        self.charset = "utf-8"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict[str, str] | None]] = []

    def get(self, url, *, params=None, headers=None, allow_redirects=None):
        self.requests.append((url, params))
        return self.responses.pop(0)


def test_ckan_api_redirect_is_followed_with_query_only_once() -> None:
    install_redirecting_json_client()
    session = _Session(
        [
            _Response(
                "https://ckan.a2gov.org/api/3/action/package_search?rows=1",
                status=308,
                location="https://ckan.a2gov.org/api/3/action/package_search/?rows=1",
            ),
            _Response(
                "https://ckan.a2gov.org/api/3/action/package_search/?rows=1",
                status=200,
                payload={"success": True, "result": {"results": [{}]}},
            ),
        ]
    )
    client = JsonClient(session, "https://ckan.a2gov.org")

    with (
        patch.object(client, "_async_validate_host", AsyncMock()),
        patch(
            "custom_components.open_data.providers.redirecting_json.async_validate_public_url",
            AsyncMock(side_effect=lambda url: url),
        ),
    ):
        payload = asyncio.run(
            client.async_get_json(
                "/api/3/action/package_search",
                params={"rows": "1"},
            )
        )

    assert payload["success"] is True
    assert session.requests == [
        (
            "https://ckan.a2gov.org/api/3/action/package_search",
            {"rows": "1"},
        ),
        (
            "https://ckan.a2gov.org/api/3/action/package_search/?rows=1",
            None,
        ),
    ]


def test_socrata_catalog_can_redirect_to_regional_discovery_host() -> None:
    install_redirecting_json_client()
    session = _Session(
        [
            _Response(
                "https://data.michigan.gov/api/catalog/v1",
                status=302,
                location=(
                    "https://api.us.socrata.com/api/catalog/v1"
                    "?search_context=data.michigan.gov&limit=1"
                ),
            ),
            _Response(
                "https://api.us.socrata.com/api/catalog/v1"
                "?search_context=data.michigan.gov&limit=1",
                status=200,
                payload={"results": [], "resultSetSize": 0},
            ),
        ]
    )
    client = JsonClient(session, "https://data.michigan.gov")

    with (
        patch.object(client, "_async_validate_host", AsyncMock()),
        patch(
            "custom_components.open_data.providers.redirecting_json.async_validate_public_url",
            AsyncMock(side_effect=lambda url: url),
        ) as validate,
    ):
        payload = asyncio.run(
            client.async_get_json(
                "/api/catalog/v1",
                params={"search_context": "data.michigan.gov", "limit": "1"},
            )
        )

    assert payload == {"results": [], "resultSetSize": 0}
    assert validate.await_count == 2
    assert session.requests[1][1] is None
