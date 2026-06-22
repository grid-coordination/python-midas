"""Authentication utilities for the MIDAS API."""

from __future__ import annotations

from typing import Any, Generator

import httpx
import pendulum


class BearerAuth(httpx.Auth):
    """httpx Auth subclass that injects a Bearer token."""

    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class BasicAuth(httpx.Auth):
    """httpx Auth subclass that injects HTTP Basic auth."""

    def __init__(self, username: str, password: str) -> None:
        import base64

        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        self._header_value = f"Basic {encoded}"

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = self._header_value
        yield request


def get_token(
    username: str,
    password: str,
    url: str = "https://midasapi.energy.ca.gov/api",
) -> dict[str, Any]:
    """Authenticate with MIDAS using HTTP Basic auth and return token info.

    The token is returned in the `Token` response header and is valid for
    10 minutes. Returns a dict with token, acquired_at, and expires_at.

    Raises httpx.HTTPStatusError on failure.
    """
    import base64

    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

    timeout = httpx.Timeout(30.0, connect=30.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{url}/Token",
            headers={"Authorization": f"Basic {encoded}"},
        )
        resp.raise_for_status()

    token = resp.headers.get("token") or resp.headers.get("Token")
    now = pendulum.now("UTC")

    return {
        "token": token,
        "acquired_at": now,
        "expires_at": now.add(seconds=600),
    }


def token_expired(token_info: dict[str, Any], buffer_seconds: int = 30) -> bool:
    """True if a token-info dict is expired or will expire within buffer_seconds."""
    expires_at = token_info.get("expires_at")
    if expires_at is None:
        return True
    now = pendulum.now("UTC")
    return now >= expires_at.subtract(seconds=buffer_seconds)


class AutoTokenAuth(httpx.Auth):
    """httpx Auth that auto-refreshes the MIDAS bearer token when expired."""

    def __init__(
        self,
        username: str,
        password: str,
        url: str = "https://midasapi.energy.ca.gov/api",
        buffer_seconds: int = 30,
    ) -> None:
        self.username = username
        self.password = password
        self.url = url
        self.buffer_seconds = buffer_seconds
        self.token_info: dict[str, Any] = get_token(username, password, url)

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        if token_expired(self.token_info, self.buffer_seconds):
            self.token_info = get_token(self.username, self.password, self.url)
        request.headers["Authorization"] = f"Bearer {self.token_info['token']}"
        yield request
