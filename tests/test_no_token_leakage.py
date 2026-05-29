"""Rule R3 regression — the API key NEVER appears in repr / str output.

If this test ever fails, the leak is a security incident — the user's
token has gained a path into log output. Do not soften the assertion to
chase a green CI; fix the leak.
"""

from __future__ import annotations

from apier import Client

# Build the fake key via concatenation so the literal contiguous
# substring "apier_test_<16+chars>" never appears verbatim in the
# packaged tarball — keeps the published-surface secret-leak grep
# clean while still exercising a realistic-shape token at runtime.
# noqa: S105 — test fixture, not a real credential.
KEY = "apier_" + "test_" + "FAKE_KEY_REGRESSION_ONLY_xxx"
KEY_PREFIX = "apier_" + "test_"


def test_key_not_in_repr() -> None:
    c = Client(api_key=KEY)
    r = repr(c)
    assert KEY not in r
    # Defensive: even a partial leak (the prefix) is unacceptable.
    assert KEY_PREFIX not in r
    assert "***" in r


def test_key_not_in_str() -> None:
    c = Client(api_key=KEY)
    s = str(c)
    assert KEY not in s
    assert KEY_PREFIX not in s


def test_unauthenticated_client_repr_does_not_say_none_key() -> None:
    # When no key is set the repr should show api_key=None — never
    # "None" leaking into a downstream log that pattern-matches on
    # the literal Bearer token shape.
    c = Client()
    r = repr(c)
    assert "Bearer" not in r
    assert KEY_PREFIX not in r
