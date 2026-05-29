#!/usr/bin/env python3
"""Altinn 2 -> Altinn 3 migration map example.

Calls the zero-auth Category-A endpoint via the apier-no Python package
and prints the response JSON. Exits non-zero if the response is missing
the documented data.mappings field — that doubles as the assertion gate
for CI's positive-control job, which re-runs this script against a
known-404 path and verifies it exits non-zero (not 0).
"""

from __future__ import annotations

import json
import os
import sys

from apier import ApierError, Client


def main() -> int:
    base_url = os.environ.get("APIER_BASE_URL", "https://www.apier.no")
    try:
        client = Client(base_url=base_url)
        body = client.get("/api/v1/tools/altinn-migration")
    except ApierError as e:
        # Structured error path — surface error_code + summary, exit
        # non-zero so the CI positive-control job stays correct.
        print(f"Apier error: {e}", file=sys.stderr)
        return 1
    except (ValueError, Exception) as e:  # noqa: BLE001 - example script
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    mappings = body.get("data", {}).get("mappings")
    if not mappings:
        print("No mappings in response", file=sys.stderr)
        return 1

    print(json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
