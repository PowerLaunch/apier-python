"""Offline request tests — mock urllib's opener, never touch the network.

Rule R10: tests must run without any live network. The mock opener returns
pre-canned responses; the client's parse + envelope-mapping logic is what
this file exercises.
"""

from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from apier import ApierError, Client

# --- helpers -----------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for an HTTPResponse instance returned by opener.open()."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _patch_opener(client: Client, return_value: _FakeResponse) -> MagicMock:
    """Replace the client's opener with a MagicMock that yields return_value."""
    mock = MagicMock()
    mock.open.return_value = return_value
    client._opener = mock  # type: ignore[assignment]
    return mock


def _patch_opener_raises(client: Client, exc: BaseException) -> MagicMock:
    mock = MagicMock()
    mock.open.side_effect = exc
    client._opener = mock  # type: ignore[assignment]
    return mock


# --- happy path -------------------------------------------------------------


def test_get_returns_parsed_dict() -> None:
    c = Client()
    body = json.dumps({"data": {"mappings": [{"old": "1", "new": "2"}]}}).encode()
    _patch_opener(c, _FakeResponse(200, body))
    out = c.get("/api/v1/tools/altinn-migration")
    assert isinstance(out, dict)
    assert out["data"]["mappings"][0]["old"] == "1"


def test_get_passes_default_timeout() -> None:
    c = Client(timeout=12.5)
    body = json.dumps({"data": "ok"}).encode()
    mock = _patch_opener(c, _FakeResponse(200, body))
    c.get("/api/v1/capabilities")
    # opener.open(req, timeout=...) — second positional is the timeout
    _, kwargs = mock.open.call_args
    assert kwargs["timeout"] == 12.5


def test_get_passes_per_call_timeout_override() -> None:
    c = Client(timeout=30.0)
    body = json.dumps({"data": "ok"}).encode()
    mock = _patch_opener(c, _FakeResponse(200, body))
    c.get("/api/v1/capabilities", timeout=2.5)
    _, kwargs = mock.open.call_args
    assert kwargs["timeout"] == 2.5


def test_get_attaches_bearer_when_api_key_set() -> None:
    c = Client(api_key="apier_test_fake_xyz")
    body = json.dumps({"data": "ok"}).encode()
    mock = _patch_opener(c, _FakeResponse(200, body))
    c.get("/api/v1/company/999999999/context")
    req = mock.open.call_args.args[0]
    # Authorization is exactly "Bearer <key>". The key never appears
    # in any other header or any logging surface.
    assert req.get_header("Authorization") == "Bearer apier_test_fake_xyz"


def test_get_omits_bearer_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APIER_API_KEY", raising=False)
    c = Client()
    body = json.dumps({"data": "ok"}).encode()
    mock = _patch_opener(c, _FakeResponse(200, body))
    c.get("/api/v1/tools/altinn-migration")
    req = mock.open.call_args.args[0]
    # Category A endpoints get no Authorization header at all.
    assert req.get_header("Authorization") is None


def test_get_sets_user_agent_and_accept() -> None:
    c = Client()
    body = json.dumps({"data": "ok"}).encode()
    mock = _patch_opener(c, _FakeResponse(200, body))
    c.get("/api/v1/capabilities")
    req = mock.open.call_args.args[0]
    ua = req.get_header("User-agent")
    assert ua is not None
    assert ua.startswith("apier-python/")
    # Rule R9 — no PII, no email, no repo URL in the UA string.
    assert "@" not in ua
    assert "github.com" not in ua
    assert req.get_header("Accept") == "application/json"


def test_get_handles_204_empty_body() -> None:
    c = Client()
    _patch_opener(c, _FakeResponse(204, b""))
    out = c.get("/api/v1/something/empty")
    assert out == {}


def test_per_call_timeout_must_be_positive() -> None:
    c = Client()
    body = json.dumps({"data": "ok"}).encode()
    _patch_opener(c, _FakeResponse(200, body))
    with pytest.raises(ValueError, match="timeout must be"):
        c.get("/api/v1/capabilities", timeout=0)


# --- error path -------------------------------------------------------------


def _http_error(
    status: int,
    body: dict[str, Any] | bytes | None,
    reason: str = "Boom",
) -> urllib.error.HTTPError:
    if body is None:
        payload = b""
    elif isinstance(body, dict):
        payload = json.dumps(body).encode()
    else:
        payload = body
    return urllib.error.HTTPError(
        url="https://www.apier.no/blocked",
        code=status,
        msg=reason,
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(payload),
    )


def test_structured_envelope_maps_to_apier_error() -> None:
    c = Client()
    body = {
        "success": False,
        "error_code": "VALIDATION_FAILED",
        "explanation": {
            "summary": "Invalid org_number",
            "why": "Must be 9 digits.",
            "fix_steps": ["Re-send with a 9-digit org_number."],
        },
    }
    _patch_opener_raises(c, _http_error(400, body))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/company/bogus/context")
    err = exc_info.value
    assert err.error_code == "VALIDATION_FAILED"
    assert err.explanation == "Invalid org_number"
    assert err.status == 400
    assert err.raw_explanation is not None
    assert err.raw_explanation["fix_steps"] == ["Re-send with a 9-digit org_number."]


def test_404_with_no_body_falls_back_to_synthetic_code() -> None:
    c = Client()
    _patch_opener_raises(c, _http_error(404, None, reason="Not Found"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/something/missing")
    err = exc_info.value
    assert err.error_code == "HTTP_404"
    assert err.explanation == "Not Found"
    assert err.status == 404


def test_html_error_body_does_not_crash() -> None:
    c = Client()
    html_body = b"<html><body>Bad Gateway</body></html>"
    _patch_opener_raises(c, _http_error(502, html_body, reason="Bad Gateway"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/health")
    err = exc_info.value
    # Synthetic HTTP_502 because the body wasn't parseable JSON.
    assert err.error_code == "HTTP_502"
    assert err.status == 502


def test_non_object_json_body_falls_back() -> None:
    c = Client()
    _patch_opener_raises(c, _http_error(500, b'["array", "not", "object"]', reason="Server Error"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/health")
    err = exc_info.value
    assert err.error_code == "HTTP_500"
    assert err.status == 500


def test_url_error_maps_to_network_error_apier_error() -> None:
    c = Client()
    _patch_opener_raises(c, urllib.error.URLError("dns failure"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/capabilities")
    err = exc_info.value
    assert err.error_code == "NETWORK_ERROR"
    assert err.status is None
    # Reason text only — Rule R6 forbids the raw URL leaking through.
    assert "https://" not in err.explanation


def test_apier_error_text_does_not_leak_response_body() -> None:
    # The upstream body contains a token-shaped string; the exception
    # must not include the raw body anywhere. Rule R6.
    # Build the byte literal via concatenation so the contiguous
    # `apier_live_<16+chars>` substring never appears verbatim in
    # the packaged tarball (keeps the published-surface secret-leak
    # grep clean while still exercising the realistic-shape case).
    c = Client()
    fake_token = (b"apier_" + b"live_" + b"FAKE_TOKEN_LEAK_TEST_xxx")
    nasty = b'{"error":"see Bearer ' + fake_token + b'"}'
    _patch_opener_raises(c, _http_error(403, nasty, reason="Forbidden"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/company/999999999/context")
    err = exc_info.value
    full = f"{err.error_code}|{err.explanation}|{err.status}"
    assert "apier_live_" not in full
    assert "Bearer " not in full


def test_2xx_with_non_json_body_raises_apier_error() -> None:
    c = Client()
    _patch_opener(c, _FakeResponse(200, b"<html>not json</html>"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/anything")
    err = exc_info.value
    assert err.error_code == "HTTP_200"
    assert err.status == 200


def test_2xx_with_array_body_raises_apier_error() -> None:
    c = Client()
    _patch_opener(c, _FakeResponse(200, b"[1,2,3]"))
    with pytest.raises(ApierError) as exc_info:
        c.get("/api/v1/anything")
    err = exc_info.value
    assert err.error_code == "HTTP_200"


# --- iterability sanity -----------------------------------------------------


def _flattened_keys(d: dict[str, Any]) -> Iterator[str]:
    for k, v in d.items():
        yield k
        if isinstance(v, dict):
            yield from _flattened_keys(v)


def test_returns_plain_dict_callers_can_iterate() -> None:
    c = Client()
    body = json.dumps(
        {"_meta": {"rulebook_version": "2026.2.1"}, "data": {"x": 1}}
    ).encode()
    _patch_opener(c, _FakeResponse(200, body))
    out = c.get("/api/v1/tools/anything")
    assert "_meta" in list(_flattened_keys(out))
