# apier-no

Official Python client for [Apier](https://www.apier.no) — Norwegian compliance infrastructure API.

- **Zero runtime dependencies.** Pure Python stdlib (`urllib`, `ssl`, `json`).
- **HTTPS-only**, with defence-in-depth against open redirects.
- **Typed** (`py.typed`), `mypy --strict` clean.
- Python 3.11+.

## Install

```bash
pip install apier-no
```

## Quickstart

```python
from apier import Client, ApierError

# Zero-auth — works against every Category-A endpoint
# (/api/v1/tools/*, /api/v1/public/*, /api/v1/capabilities).
client = Client()
data = client.get("/api/v1/tools/altinn-migration")
print(data["data"]["mappings"][0])
```

For Category-B endpoints (company data, accounting filings, etc.) pass an API key:

```python
client = Client(api_key="apier_test_...")           # explicit
client = Client()                                   # or APIER_API_KEY env
```

Errors normalise to a structured `ApierError`:

```python
try:
    client.get("/api/v1/company/999999999/context")
except ApierError as e:
    print(e.error_code)              # e.g. "VALIDATION_FAILED"
    print(e.explanation)             # short summary
    print(e.raw_explanation)         # full {summary, why, fix_steps, legal_basis}
    print(e.status)                  # HTTP status (None on network errors)
```

## Configuration

| Argument | Default | Notes |
|---|---|---|
| `api_key` | `APIER_API_KEY` env or `None` | Empty string treated as no key. |
| `base_url` | `https://www.apier.no` | Must be `https://`. Non-https raises `ValueError`. |
| `timeout` | `30.0` (seconds) | Per-call override: `client.get(path, timeout=2.5)`. |

## Security posture

This library is intentionally conservative:

- HTTPS only. Non-https `base_url` is rejected at construction time. Non-https redirects are refused by the client's redirect handler.
- The system default SSL context (`ssl.create_default_context()`) is used unmodified. The library does not expose, accept, or expose a way to disable certificate verification or pass a custom CA bundle.
- The API key never appears in `repr()`, `str()`, exception text, or any other surface the library emits. The repr masks it as `***`.
- Errors never leak raw response bodies, headers, or request URLs.

For the full threat model and disclosure process see [SECURITY.md](SECURITY.md).

## Discovery

The Apier discovery surface points at this package:

- `https://www.apier.no/llms.txt`
- `https://www.apier.no/llms-full.txt`
- `https://www.apier.no/docs/sdks`

## Versioning + releases

- [Semantic versioning](https://semver.org/).
- The version lives in `src/apier/_version.py`. Every release CI step verifies the git tag matches.
- Published via [PEP 740 Trusted Publishing](https://docs.pypi.org/trusted-publishers/) from this repo — no long-lived PyPI token is configured anywhere.

## License

MIT — see [LICENSE](LICENSE).
