"""ApierError dataclass surface tests."""

from __future__ import annotations

from apier import ApierError


def test_minimal_construction() -> None:
    e = ApierError(error_code="X", explanation="y")
    assert e.error_code == "X"
    assert e.explanation == "y"
    assert e.raw_explanation is None
    assert e.status is None


def test_str_with_status() -> None:
    e = ApierError(error_code="VALIDATION_FAILED", explanation="bad input", status=400)
    s = str(e)
    assert "[400]" in s
    assert "VALIDATION_FAILED" in s
    assert "bad input" in s


def test_str_without_status() -> None:
    e = ApierError(error_code="NETWORK_ERROR", explanation="dns")
    s = str(e)
    assert s.startswith("NETWORK_ERROR")
    assert "dns" in s


def test_is_exception() -> None:
    e = ApierError(error_code="X", explanation="y")
    assert isinstance(e, Exception)
    try:
        raise e
    except ApierError as caught:
        assert caught.error_code == "X"
