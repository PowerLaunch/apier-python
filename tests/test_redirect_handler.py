"""Rule R7 — open-redirect defence."""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from apier._http import HttpsOnlyRedirectHandler


def _make_req() -> urllib.request.Request:
    return urllib.request.Request("https://www.apier.no/something")


def test_redirect_to_https_is_allowed() -> None:
    h = HttpsOnlyRedirectHandler()
    req = _make_req()
    new = h.redirect_request(req, None, 302, "Found", {}, "https://other.example.com/x")  # type: ignore[arg-type]
    assert new is not None
    assert new.get_full_url() == "https://other.example.com/x"


def test_redirect_to_http_is_refused() -> None:
    h = HttpsOnlyRedirectHandler()
    req = _make_req()
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, None, 302, "Found", {}, "http://attacker.example.com/x")  # type: ignore[arg-type]


def test_redirect_to_ftp_is_refused() -> None:
    h = HttpsOnlyRedirectHandler()
    req = _make_req()
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, None, 302, "Found", {}, "ftp://attacker.example.com/x")  # type: ignore[arg-type]


def test_redirect_to_data_uri_is_refused() -> None:
    h = HttpsOnlyRedirectHandler()
    req = _make_req()
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, None, 302, "Found", {}, "data:text/html,abc")  # type: ignore[arg-type]


def test_redirect_uppercase_scheme_normalised() -> None:
    # Per RFC, scheme is case-insensitive. Defence must too.
    h = HttpsOnlyRedirectHandler()
    req = _make_req()
    new = h.redirect_request(req, None, 302, "Found", {}, "HTTPS://example.com/x")  # type: ignore[arg-type]
    assert new is not None
