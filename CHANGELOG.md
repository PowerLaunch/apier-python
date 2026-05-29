# Changelog

All notable changes to `apier-no` are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-05-29

Initial release.

### Added

- `apier.Client(api_key=None, base_url="https://www.apier.no", timeout=30.0)` — thin stdlib HTTPS client.
- `Client.get(path, *, timeout=None)` returning a parsed JSON dict.
- `apier.ApierError(error_code, explanation, raw_explanation=None, status=None)` — structured error envelope.
- `apier.__version__` — single-source version pin (`src/apier/_version.py`).

### Security posture

- HTTPS-only `base_url` enforced at construction; non-https raises `ValueError`.
- Custom `HttpsOnlyRedirectHandler` refuses non-https redirects (open-redirect defence in depth).
- `ssl.create_default_context()` used unmodified; no knob to disable verification.
- `APIER_API_KEY` masked as `***` in `repr` / `str`; regression test pins it.
- Error envelope text never carries raw response bodies, headers, or request URLs.
- Zero runtime dependencies.

### Publishing

- Published to PyPI via PEP 740 Trusted Publishing (OIDC, no long-lived token).
- Release CI verifies the git tag matches `_version.py` before publishing.
- Wheel + sdist surface grepped for token-shaped strings before publish.

[0.1.0]: https://github.com/PowerLaunch/apier-python/releases/tag/v0.1.0
