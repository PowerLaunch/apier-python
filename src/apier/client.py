"""Apier HTTPS client — stdlib only.

Design rules locked at every layer (Rules R1-R15 of the project brief):

R1.  Stdlib only at runtime. No requests, no httpx, no aiohttp, no urllib3.
     If you need an alternative HTTP stack, fork; we will not add a runtime
     dep that ships to every Apier consumer.
R2.  HTTPS-only. base_url with any other scheme is rejected at __init__.
R3.  api_key never appears in repr / str / log output. The masked field on
     __repr__ is the literal string "***".
R4.  ssl.create_default_context() (in _http.py) — never disabled, never
     overridden. The library refuses to be "helpful" about broken cert
     chains.
R5.  Authorization header attached only when api_key is non-empty. Category-A
     zero-auth endpoints receive no header.
R6.  Errors normalise to ApierError(error_code, explanation). Raw bodies,
     headers, and URLs are never leaked into the exception text.
R7.  Open-redirect defence lives in _http.HttpsOnlyRedirectHandler.
R8.  Timeouts default to 30s; overridable per call; never None.
R9.  User-Agent: "apier-python/<v> (Python <pyver>; <platform>)" — no PII,
     no email, no repo URL.

Public surface:
    Client(api_key: str | None = None,
           base_url: str = "https://www.apier.no",
           timeout: float = 30.0)
    Client.get(path: str, *, timeout: float | None = None) -> dict[str, Any]
"""

from __future__ import annotations

import json
import os
import platform as _platform
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from apier._http import build_opener
from apier._version import __version__
from apier.errors import ApierError

DEFAULT_BASE_URL = "https://www.apier.no"
DEFAULT_TIMEOUT_SECONDS = 30.0


def _user_agent() -> str:
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    plat = _platform.system() or "Unknown"
    return f"apier-python/{__version__} (Python {py}; {plat})"


def _validate_base_url(url: str) -> str:
    """Reject anything not https + host. Rule R2."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise ValueError(
            f"Apier base_url must use https://; got scheme={parts.scheme!r}"
        )
    if not parts.netloc:
        raise ValueError(f"Apier base_url is missing a host: {url!r}")
    return url.rstrip("/")


def _resolve_api_key(explicit: str | None) -> str | None:
    """Return the API key from the explicit arg or APIER_API_KEY env.
    Empty string is treated as "no key" so Category-A endpoints work."""
    if explicit is not None:
        return explicit if explicit != "" else None
    env = os.environ.get("APIER_API_KEY", "")
    return env if env != "" else None


class Client:
    """Thin synchronous client over the Apier HTTPS API.

    Category-A endpoints (zero-auth: ``/api/v1/tools/*``, ``/api/v1/public/*``,
    ``/api/v1/capabilities``) work without any api_key. Category-B endpoints
    require api_key to be set, either via the ``api_key=`` constructor arg
    or the ``APIER_API_KEY`` environment variable.

    All requests time out after ``timeout`` seconds (default 30); pass
    ``timeout=`` to ``get()`` for per-call overrides.

    Examples
    --------
    >>> c = Client()                                                # zero-auth
    >>> data = c.get("/api/v1/tools/altinn-migration")              # dict
    >>> c2 = Client(api_key="apier_test_xxx")                       # Category B
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = _validate_base_url(base_url)
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0; got {timeout!r}")
        self._timeout = float(timeout)
        self._opener = build_opener()

    def __repr__(self) -> str:
        # Rule R3: the api_key NEVER appears in repr output, not even
        # the first / last few chars. The test suite pins this exactly.
        masked = "***" if self._api_key else None
        return (
            f"Client(api_key={masked!r}, base_url={self._base_url!r}, "
            f"timeout={self._timeout!r})"
        )

    # __str__ inherits from __repr__ (dataclass-like), so masking holds
    # there too without an explicit override.

    def get(
        self,
        path: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """GET ``path`` and return the parsed JSON body as a dict.

        Raises
        ------
        ApierError
            On any non-2xx status. Carries error_code + explanation
            from the upstream envelope when present, otherwise a
            synthetic HTTP_<status> + reason text.
        """
        return self._request("GET", path, timeout=timeout)

    # ----- internal -----

    def _build_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            # External absolute URLs land here; validate against R2.
            if not path.startswith("https://"):
                _raise_non_https(path)
            return _validate_base_url(path)
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", _user_agent())
        req.add_header("Accept", "application/json")
        if self._api_key:
            # Rule R5: header attached only when key is non-empty.
            # The token itself never reaches logs / repr / exception text.
            req.add_header("Authorization", f"Bearer {self._api_key}")
        effective_timeout = self._timeout if timeout is None else float(timeout)
        if effective_timeout <= 0:
            raise ValueError(f"timeout must be > 0; got {timeout!r}")

        try:
            with self._opener.open(req, timeout=effective_timeout) as resp:
                status = resp.status
                body_bytes = resp.read()
        except urllib.error.HTTPError as e:
            # Non-2xx upstream — parse the envelope into ApierError.
            raise _raise_from_http_error(e) from None
        except urllib.error.URLError as e:
            # Network / TLS / DNS failure before status line. Rule R6:
            # carry the reason text but never the full URL (could include
            # query params with sensitive context).
            raise ApierError(
                error_code="NETWORK_ERROR",
                explanation=str(e.reason),
                status=None,
            ) from None

        # 2xx happy path
        return _parse_2xx_body(status, body_bytes)


def _raise_non_https(url: str) -> None:  # pragma: no cover - signal
    raise ValueError(
        f"Apier client refuses non-https URL: {urllib.parse.urlsplit(url).scheme!r}"
    )


def _parse_2xx_body(status: int, body_bytes: bytes) -> dict[str, Any]:
    if not body_bytes:
        # 204 etc — surface an empty dict rather than failing on JSON parse.
        return {}
    try:
        parsed = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # Apier always returns JSON on 2xx; if upstream broke that
        # contract, surface as an ApierError, not a raw exception.
        raise ApierError(
            error_code=f"HTTP_{status}",
            explanation="upstream returned a non-JSON body on a 2xx response",
            status=status,
        ) from e
    if not isinstance(parsed, dict):
        raise ApierError(
            error_code=f"HTTP_{status}",
            explanation="upstream returned a non-object JSON body",
            status=status,
        )
    return parsed


def _raise_from_http_error(e: urllib.error.HTTPError) -> ApierError:
    """Map an HTTPError to a structured ApierError. Rule R6:
    NEVER include raw response body, headers, or URL in the error text."""
    status = e.code
    reason = e.reason if isinstance(e.reason, str) else str(e.reason)
    body_bytes: bytes = b""
    try:
        body_bytes = e.read() or b""
    except Exception:  # pragma: no cover - defensive
        body_bytes = b""

    if not body_bytes:
        return ApierError(
            error_code=f"HTTP_{status}",
            explanation=reason or f"HTTP {status}",
            status=status,
        )

    try:
        envelope = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ApierError(
            error_code=f"HTTP_{status}",
            explanation=reason or f"HTTP {status}",
            status=status,
        )

    if not isinstance(envelope, dict):
        return ApierError(
            error_code=f"HTTP_{status}",
            explanation=reason or f"HTTP {status}",
            status=status,
        )

    # Apier error envelope:
    #   { "success": false, "error_code": "...", "explanation": { ... } }
    code = envelope.get("error_code")
    expl = envelope.get("explanation")
    if isinstance(code, str) and isinstance(expl, dict):
        summary = expl.get("summary")
        explanation_text = (
            summary if isinstance(summary, str) else f"HTTP {status}"
        )
        return ApierError(
            error_code=code,
            explanation=explanation_text,
            raw_explanation=expl,
            status=status,
        )
    # Older / non-canonical shape — degrade gracefully.
    return ApierError(
        error_code=f"HTTP_{status}",
        explanation=reason or f"HTTP {status}",
        status=status,
    )
