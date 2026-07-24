"""SSRF-safe redirect support for provider JSON APIs."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urljoin, urlparse

from aiohttp import ClientError, ClientResponseError

from .base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .common import (
    MAX_JSON_BYTES,
    MAX_REDIRECTS,
    REQUEST_TIMEOUT,
    USER_AGENT,
    JsonClient,
    async_validate_public_url,
)


async def _async_get_json_following_redirects(
    self: JsonClient,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> Any:
    """Issue a bounded JSON GET while validating every redirect destination."""
    await self._async_validate_host()
    current = f"{self.portal_url}{path}"
    request_params = params

    for _ in range(MAX_REDIRECTS + 1):
        await async_validate_public_url(current)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    current,
                    params=request_params,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        location = response.headers.get("Location")
                        if not location:
                            raise OpenDataResponseError(
                                "Portal JSON API redirected without a destination"
                            )
                        current = urljoin(str(response.url), location)
                        parsed = urlparse(current)
                        if parsed.scheme not in {"http", "https"}:
                            raise OpenDataSecurityError(
                                "Portal JSON API redirected to a non-HTTP destination"
                            )
                        request_params = None
                        continue

                    response.raise_for_status()
                    declared_length = response.content_length
                    if declared_length is not None and declared_length > MAX_JSON_BYTES:
                        raise OpenDataResponseError(
                            f"Portal response exceeded {MAX_JSON_BYTES} bytes"
                        )
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        body.extend(chunk)
                        if len(body) > MAX_JSON_BYTES:
                            raise OpenDataResponseError(
                                f"Portal response exceeded {MAX_JSON_BYTES} bytes"
                            )
                    return json.loads(body.decode(response.charset or "utf-8"))
        except (OpenDataSecurityError, OpenDataResponseError):
            raise
        except ClientResponseError as err:
            raise OpenDataResponseError(
                f"Portal returned HTTP {err.status} for {current}"
            ) from err
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            raise OpenDataResponseError(
                f"Portal returned invalid JSON for {current}"
            ) from err
        except (ClientError, TimeoutError) as err:
            raise OpenDataConnectionError(f"Unable to reach portal: {current}") from err

    raise OpenDataResponseError("Portal JSON API returned too many redirects")


def install_redirecting_json_client() -> None:
    """Install redirect-safe JSON behavior once for every provider adapter."""
    if getattr(JsonClient.async_get_json, "_open_data_redirect_safe", False):
        return
    setattr(_async_get_json_following_redirects, "_open_data_redirect_safe", True)
    JsonClient.async_get_json = _async_get_json_following_redirects
