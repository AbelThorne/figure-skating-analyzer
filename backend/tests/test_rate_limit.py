import time
from app.auth.rate_limit import LoginRateLimiter


def test_allows_under_limit():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.is_allowed("a@b.com") is True
    limiter.record("a@b.com")
    limiter.record("a@b.com")
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False


def test_different_emails_independent():
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=60)
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False
    assert limiter.is_allowed("c@d.com") is True


def test_window_expires():
    limiter = LoginRateLimiter(max_attempts=1, window_seconds=0.1)
    limiter.record("a@b.com")
    assert limiter.is_allowed("a@b.com") is False
    time.sleep(0.15)
    assert limiter.is_allowed("a@b.com") is True
