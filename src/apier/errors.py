"""Apier error envelope.

ApierError wraps every non-2xx response from the API. The error_code is the
machine-readable identifier from the documented Apier error envelope; the
explanation is the human-readable summary. The full structured Explanation
object (with why / fix_steps / relevant_link / legal_basis) is exposed as
the raw_explanation dict for callers who want it.

NEVER includes raw response bodies, headers, or request URLs — Rule R6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApierError(Exception):
    """Structured Apier API error.

    Attributes
    ----------
    error_code : str
        Machine-readable error code (e.g. "VALIDATION_FAILED",
        "HITL_NOT_FOUND", "HTTP_404"). On JSON parse failure of the
        upstream body, this is the synthetic "HTTP_<status>" form.
    explanation : str
        Short human-readable summary suitable for logs / surfaces.
    raw_explanation : dict[str, Any] | None
        The complete server-side Explanation object when available
        (contains why, fix_steps, relevant_link, legal_basis on
        live Apier errors). None when the upstream returned no
        parseable envelope.
    status : int | None
        HTTP status code, when known. None on network errors that
        never reach the status line.
    """

    error_code: str
    explanation: str
    raw_explanation: dict[str, Any] | None = field(default=None, repr=False)
    status: int | None = field(default=None)

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.status is not None:
            return f"[{self.status}] {self.error_code}: {self.explanation}"
        return f"{self.error_code}: {self.explanation}"
