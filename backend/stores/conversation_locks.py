"""같은 통화의 읽기·분석·쓰기를 직렬화한다. 단일 프로세스 전용이다."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock, RLock


class ConversationLocks:
    def __init__(self) -> None:
        self._guard = Lock()
        self._entries: dict[str, tuple[RLock, int]] = {}

    @contextmanager
    def hold(self, conversation_id: str) -> Iterator[None]:
        # 대기 중인 요청도 세어 마지막 요청이 나갈 때만 잠금을 제거한다.
        with self._guard:
            lock, users = self._entries.get(conversation_id, (None, 0))
            if lock is None:
                lock = RLock()
            self._entries[conversation_id] = (lock, users + 1)
        try:
            with lock:
                yield
        finally:
            with self._guard:
                _, users = self._entries[conversation_id]
                if users == 1:
                    del self._entries[conversation_id]
                else:
                    self._entries[conversation_id] = (lock, users - 1)
