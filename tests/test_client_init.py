"""Constructor + URL validation tests."""

from __future__ import annotations

import os

import pytest

from apier import Client
from apier.client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    _resolve_api_key,
    _validate_base_url,
)


def test_default_base_url_and_timeout() -> None:
    c = Client()
    assert c._base_url == DEFAULT_BASE_URL
    assert c._timeout == DEFAULT_TIMEOUT_SECONDS


def test_https_only_rejects_http() -> None:
    with pytest.raises(ValueError, match="https"):
        Client(base_url="http://example.com")


def test_https_only_rejects_ftp() -> None:
    with pytest.raises(ValueError, match="https"):
        Client(base_url="ftp://example.com")


def test_rejects_url_without_host() -> None:
    with pytest.raises(ValueError, match="missing a host"):
        Client(base_url="https://")


def test_validate_base_url_strips_trailing_slash() -> None:
    assert _validate_base_url("https://www.apier.no/") == "https://www.apier.no"


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="timeout must be"):
        Client(timeout=0)
    with pytest.raises(ValueError, match="timeout must be"):
        Client(timeout=-1.5)


def test_resolve_api_key_explicit_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIER_API_KEY", "env-value")
    assert _resolve_api_key("explicit-value") == "explicit-value"


def test_resolve_api_key_explicit_empty_treated_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APIER_API_KEY", "env-value")
    # Explicit empty string overrides env and returns None — user is
    # deliberately requesting an unauthenticated client.
    assert _resolve_api_key("") is None


def test_resolve_api_key_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIER_API_KEY", "from-env")
    assert _resolve_api_key(None) == "from-env"


def test_resolve_api_key_env_empty_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APIER_API_KEY", "")
    assert _resolve_api_key(None) is None


def test_resolve_api_key_no_env_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APIER_API_KEY", raising=False)
    assert _resolve_api_key(None) is None


def test_build_url_relative_path() -> None:
    c = Client()
    assert c._build_url("/api/v1/tools/altinn-migration") == (
        "https://www.apier.no/api/v1/tools/altinn-migration"
    )


def test_build_url_path_without_leading_slash() -> None:
    c = Client()
    assert c._build_url("api/v1/capabilities") == (
        "https://www.apier.no/api/v1/capabilities"
    )


def test_build_url_external_https_url_is_kept() -> None:
    c = Client()
    # Absolute https URL is validated and kept (the call still goes through
    # the client's https-only opener + redirect handler).
    assert c._build_url("https://other.example.com/foo") == (
        "https://other.example.com/foo"
    )


def test_constructor_with_apier_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APIER_API_KEY", "apier_test_fake_key_zzz")
    c = Client()
    assert c._api_key == "apier_test_fake_key_zzz"


def test_constructor_explicit_api_key_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APIER_API_KEY", "env-value")
    c = Client(api_key="explicit-key")
    assert c._api_key == "explicit-key"


def test_constructor_no_api_key_when_env_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APIER_API_KEY", raising=False)
    c = Client()
    assert c._api_key is None
    # Sanity: nothing about the key sneaks into the repr either.
    assert "apier_" not in repr(c).lower()
    assert "bearer" not in repr(c).lower()


def test_env_isolation_between_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    # Verify each Client snapshot of the env stays put: changing the
    # env after construction must not retroactively change the client.
    monkeypatch.setenv("APIER_API_KEY", "first")
    c1 = Client()
    monkeypatch.setenv("APIER_API_KEY", "second")
    c2 = Client()
    assert c1._api_key == "first"
    assert c2._api_key == "second"


def test_apier_api_key_env_does_not_persist_in_os_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sanity that the test fixtures aren't leaking. Independent of the
    # client; just keeps the suite honest.
    monkeypatch.delenv("APIER_API_KEY", raising=False)
    assert "APIER_API_KEY" not in os.environ
