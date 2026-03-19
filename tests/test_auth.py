"""Auth and token tests."""

from __future__ import annotations

import pendulum

from midas.auth import BasicAuth, BearerAuth, token_expired


def test_bearer_auth_header():
    auth = BearerAuth("my-token-123")
    assert auth.token == "my-token-123"


def test_basic_auth_header():
    auth = BasicAuth("user", "pass")
    # Should produce Base64("user:pass") = "dXNlcjpwYXNz"
    assert auth._header_value == "Basic dXNlcjpwYXNz"


def test_token_expired_true():
    past = pendulum.now("UTC").subtract(minutes=15)
    info = {"token": "abc", "acquired_at": past, "expires_at": past.add(seconds=600)}
    assert token_expired(info) is True


def test_token_expired_false():
    now = pendulum.now("UTC")
    info = {
        "token": "abc",
        "acquired_at": now,
        "expires_at": now.add(seconds=600),
    }
    assert token_expired(info) is False


def test_token_expired_within_buffer():
    now = pendulum.now("UTC")
    info = {
        "token": "abc",
        "acquired_at": now.subtract(seconds=580),
        "expires_at": now.add(seconds=20),
    }
    # 20 seconds left, buffer is 30 → should be expired
    assert token_expired(info, buffer_seconds=30) is True
    # buffer is 10 → should not be expired
    assert token_expired(info, buffer_seconds=10) is False


def test_token_expired_missing_expires_at():
    info = {"token": "abc"}
    assert token_expired(info) is True
