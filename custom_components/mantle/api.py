"""REST and WebSocket access to the Mantle hub with a long-lived token (`Authorization: Bearer mh_…`)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlsplit

import aiohttp

#: Hub action names: `<extension>.<name>` (e.g. `devices.command`); nothing that could leave the path.
ACTION_NAME = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")


class MantleError(Exception):
    """The hub could not be reached or answered with an error."""


class MantleAuthError(MantleError):
    """The hub rejected the token."""


def normalize_url(url: str) -> str:
    """`https://host/` → `https://host`; raises ValueError for anything that is not an http(s) URL."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("http:// oder https:// erwartet")
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"


class MantleClient:
    """Talks to one hub; the session belongs to Home Assistant."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = normalize_url(url)
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, payload: Any = None) -> Any:
        try:
            async with self._session.request(
                method, self.url + path, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status in (401, 403):
                    raise MantleAuthError(f"Der Hub lehnt das Token ab ({resp.status})")
                text = await resp.text()
                body = json.loads(text) if text else None
                if resp.status >= 400:
                    message = (body or {}).get("error", {}).get("message") if isinstance(body, dict) else None
                    raise MantleError(message or f"Hub antwortet {resp.status}")
                return body
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MantleError(f"Hub nicht erreichbar: {err}") from err

    async def me(self) -> dict[str, Any]:
        """The account behind the token (`role` is admin or member)."""
        return await self._request("GET", "/api/me")

    async def devices(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/ext/devices/list")

    async def call_action(self, name: str, data: dict[str, Any]) -> Any:
        """Runs a hub action; returns its result."""
        if not ACTION_NAME.match(name):
            raise MantleError(f"Ungültiger Aktionsname {name!r}")
        body = await self._request("POST", f"/api/actions/{quote(name)}", payload=data)
        return body.get("result") if isinstance(body, dict) else None

    def live(self) -> Any:
        """`/api/live` as an aiohttp WebSocket context manager."""
        ws_url = "ws" + self.url[len("http") :] + "/api/live"
        return self._session.ws_connect(
            ws_url, headers=self._headers, heartbeat=30, timeout=aiohttp.ClientWSTimeout(ws_close=10)
        )
