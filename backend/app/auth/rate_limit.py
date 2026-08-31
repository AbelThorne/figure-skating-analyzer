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

# Formulaire public de demande de compte : plus strict que le login, il est
# ouvert à tous et permettrait sinon d'énumérer les licences du club.
account_request_limiter = LoginRateLimiter(max_attempts=3, window_seconds=3600.0)

# Rattachement d'un patineur par un compte déjà connecté : le compte est
# authentifié, mais sans plafond il pourrait tester les licences du club une
# à une jusqu'à trouver une date de naissance valide.
skater_attach_limiter = LoginRateLimiter(max_attempts=5, window_seconds=3600.0)
