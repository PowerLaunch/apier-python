"""Internal HTTPS-only request helpers.

Why a separate module: keeps Client.do() small and lets us pin one piece
of defence-in-depth (the HTTPS-only redirect handler) in a place where
the test suite can target it directly.

Hard rules locked here (Rules R2, R4, R7):
  * HTTPS-only. No http://, even on redirect chains.
  * ssl.create_default_context() with NO overrides — no check_hostname=False,
    no CERT_NONE, no custom CA bundle plumbing. If a deployment needs that,
    the caller should fork the package; we will not paper over a broken
    cert chain at the library level.
  * Bearer headers never logged. Tokens never inspected, masked, or echoed.
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from typing import Any, cast


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject any redirect whose target scheme is not https.

    Defence in depth against open-redirect attacks: even if the API ever
    accidentally emits a redirect to an http:// host (or an attacker-
    controlled non-https URL), urllib raises and the call surfaces as a
    failure rather than silently downgrading to cleartext + leaking the
    Authorization header to a third party. The library refuses to follow.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.lower().startswith("https://"):
            raise urllib.error.HTTPError(
                req.get_full_url(),
                code,
                f"refused non-https redirect to {newurl!r}",
                cast(Any, headers),
                None,
            )
        # urllib's super signature is the same shape; cast is for the typeshed
        # mismatch between `object` and the internal types in the parent class.
        return super().redirect_request(
            req,
            cast(Any, fp),
            code,
            msg,
            cast(Any, headers),
            newurl,
        )


def build_opener() -> urllib.request.OpenerDirector:
    """Return an OpenerDirector wired with the https-only redirect handler
    and the system default SSL context (no overrides)."""
    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)
    return urllib.request.build_opener(https_handler, HttpsOnlyRedirectHandler())
