import time
from collections import defaultdict


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: float = 60.0):
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> None:
        cutoff = time.monotonic() - self._window
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

    def is_allowed(self, email: str) -> bool:
        self._prune(email)
        return len(self._attempts[email]) < self._max

    def record(self, email: str) -> None:
        self._attempts[email].append(time.monotonic())


# Singleton used by auth routes
login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=60.0)
