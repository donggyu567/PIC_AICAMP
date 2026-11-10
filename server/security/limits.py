"""단일 서버 프로세스에서 사용하는 요청 및 음성 연결 제한."""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


class WindowLimiter:
    """키별 최근 시간 구간의 요청 수를 제한한다."""

    def __init__(self, limit: int, window_seconds: int, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._entries: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            if key not in self._entries and len(self._entries) >= self.max_keys:
                self._entries.popitem(last=False)
            entries = self._entries.setdefault(key, deque())
            self._entries.move_to_end(key)
            while entries and entries[0] <= now - self.window_seconds:
                entries.popleft()
            if len(entries) >= self.limit:
                return False
            entries.append(now)
            return True

    def blocked(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            entries = self._entries.get(key)
            if entries is None:
                return False
            while entries and entries[0] <= now - self.window_seconds:
                entries.popleft()
            if not entries:
                del self._entries[key]
                return False
            return len(entries) >= self.limit


class SessionLimiter:
    """실시간 STT 연결을 기기별·서버 전체 기준으로 제한한다."""

    def __init__(self, per_device: int, total: int) -> None:
        self.per_device = per_device
        self.total = total
        self._active: dict[str, int] = {}
        self._count = 0
        self._lock = Lock()

    def acquire(self, owner: str) -> bool:
        with self._lock:
            if self._count >= self.total or self._active.get(owner, 0) >= self.per_device:
                return False
            self._active[owner] = self._active.get(owner, 0) + 1
            self._count += 1
            return True

    def release(self, owner: str) -> None:
        with self._lock:
            count = self._active.get(owner, 0)
            if count <= 0:
                return
            if count == 1:
                del self._active[owner]
            else:
                self._active[owner] = count - 1
            self._count -= 1


# 시연 환경의 임시 기본값. 실제 사용량에 맞춰 조정해야 한다.
invalid_auth_attempts = WindowLimiter(limit=30, window_seconds=60)
device_registrations = WindowLimiter(limit=5, window_seconds=3600)
total_device_registrations = WindowLimiter(limit=100, window_seconds=3600)
analysis_requests = WindowLimiter(limit=30, window_seconds=60)
stt_sessions = SessionLimiter(per_device=2, total=20)
