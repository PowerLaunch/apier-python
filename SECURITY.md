# Security policy — apier-no (Python)

## Threat model

This package is a thin synchronous HTTPS client over the Apier API. It does not store credentials, manage configuration files, or process Norwegian compliance data locally — every business decision happens server-side at `https://www.apier.no`.

### What we defend against

1. **API key leakage via diagnostic output.** `APIER_API_KEY` is masked as `***` in `Client.__repr__` / `Client.__str__`. A regression test pins this exactly so the key cannot regain a path into log output without breaking CI.
2. **API key leakage via exception text.** `ApierError` carries only the parsed `error_code` + summary `explanation` + HTTP status. Raw response bodies, headers, and request URLs are never embedded in the exception — even when the upstream body happens to contain a token-shaped string.
3. **Mistargeted endpoints.** `base_url` with any scheme other than `https://` is rejected at construction time. The custom `HttpsOnlyRedirectHandler` refuses to follow any redirect whose target scheme is not `https://`, even if the API ever accidentally emits one — defence in depth against open-redirect attacks that could leak the Authorization header to a third party.
4. **Cert chain tampering.** The client uses `ssl.create_default_context()` with no overrides. There is no `verify=False` knob, no custom CA bundle parameter, and no environment variable that disables verification. A user with a broken cert chain must fix the chain or fork.
5. **Supply-chain drift.** Zero runtime dependencies — stdlib only (`urllib`, `ssl`, `json`, `dataclasses`, `typing`). The published wheel + sdist are scanned in CI for token-shaped strings before publish, and a separate fork-publish guard ensures the Trusted Publishing OIDC flow only runs on the canonical `PowerLaunch/apier-python` repo.
6. **Long-lived publish secrets.** Releases use [PEP 740 Trusted Publishing](https://docs.pypi.org/trusted-publishers/) via GitHub OIDC. No PyPI token is stored anywhere — not in repo secrets, not in environment, not in any developer's `~/.pypirc`.

### Residual risks (accepted, documented)

These sit at the host layer and are out of scope for the library:

1. **Shell history.** Setting `APIER_API_KEY=apier_test_…` inline on the command line will record the key in your shell history. Prefer per-session `export` from a non-recorded file, or a secret manager.
2. **CI logs.** If you echo `os.environ["APIER_API_KEY"]` from a script, the value will land in CI logs verbatim. The library never does that itself.
3. **Local process inspection.** On multi-user systems, `ps eww` or equivalent can reveal environment variables to local users with sufficient privilege. The library runs in user space; it cannot defend against an attacker who already has user-level shell access on your machine.
4. **HTTPS proxies that terminate TLS.** Corporate MITM proxies with locally trusted CAs will be accepted by the system default SSL context — that is the host operator's policy choice, not the library's. The library has no knob to opt out of the system CA store.

## Reporting a vulnerability

Email **security@apier.no**.

Please include reproduction steps and the version of `apier-no` you tested against (`python -c "import apier; print(apier.__version__)"`). We aim to acknowledge within 48 hours and to publish a fix within 7 days for high-severity issues.

Do not file public GitHub issues for security reports.
