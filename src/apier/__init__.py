"""Apier — Norwegian compliance infrastructure API.

Stdlib-only Python client for the Apier API. ZERO runtime dependencies.

Public surface:

    from apier import Client, ApierError
    c = Client()                                    # zero-auth Category-A
    c = Client(api_key="apier_test_...")            # Bearer-authenticated

    data = c.get("/api/v1/tools/altinn-migration")  # dict

    try:
        c.get("/api/v1/company/999999999/context")
    except ApierError as e:
        print(e.error_code, e.explanation)
"""

from apier._version import __version__
from apier.client import Client
from apier.errors import ApierError

__all__ = ["__version__", "Client", "ApierError"]
