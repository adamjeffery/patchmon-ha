"""Read-only client for the PatchMon scoped API."""

from __future__ import annotations

import base64
from typing import Any

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class PatchMonError(Exception):
    """Base error for PatchMon requests."""


class PatchMonConnectionError(PatchMonError):
    """The server could not be reached or did not answer like PatchMon."""


class PatchMonAuthError(PatchMonError):
    """The credential was rejected or lacks the required access."""


class PatchMonClient:
    """Talks to one PatchMon server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token_key: str,
        token_secret: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base = f"{url.rstrip('/')}/api/v1"
        credential = base64.b64encode(f"{token_key}:{token_secret}".encode()).decode()
        self._headers = {"Authorization": f"Basic {credential}"}

    async def _get(self, path: str, **params: str) -> dict[str, Any]:
        """Read from the scoped API."""
        try:
            async with self._session.get(
                f"{self._base}/api{path}",
                headers=self._headers,
                params=params,
                timeout=_TIMEOUT,
            ) as resp:
                # Unknown paths get the web UI's HTML with a 200, which fails here
                # because this requires a JSON content type.
                try:
                    body = await resp.json()
                except (aiohttp.ContentTypeError, ValueError):
                    if resp.status < 400:
                        raise PatchMonConnectionError(
                            "The server did not return PatchMon API JSON"
                        ) from None
                    body = {}
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PatchMonConnectionError(f"Could not reach PatchMon: {err}") from err

        if not isinstance(body, dict):
            body = {}
        if status in (401, 403):
            raise PatchMonAuthError(body.get("error", "API credential rejected"))
        if status >= 400:
            raise PatchMonError(body.get("error", f"PatchMon returned HTTP {status}"))
        return body

    async def async_get_hosts(self) -> list[dict[str, Any]]:
        """Return all hosts with their update counts."""
        body = await self._get("/hosts", include="stats")
        return body.get("hosts", [])

    async def async_get_outdated_packages(self, host_id: str) -> list[dict[str, Any]]:
        """Return the packages with pending updates on one host."""
        body = await self._get(f"/hosts/{host_id}/packages", updates_only="true")
        return body.get("packages", [])
