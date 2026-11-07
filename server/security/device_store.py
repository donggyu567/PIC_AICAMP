"""기기 인증 정보와 통화 소유 관계를 저장한다. 단일 서버 프로세스 전용."""

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from threading import Lock


class DeviceStoreError(RuntimeError):
    """인증 저장소를 읽거나 쓸 수 없다."""


class ConversationOwnershipError(PermissionError):
    """해당 기기가 통화에 접근할 수 없다."""


class DeviceStore:
    """원본 토큰은 최초 발급 시 반환하고 서버에는 해시만 저장한다."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"devices": {}, "conversations": {}}
        except (OSError, ValueError) as error:
            raise DeviceStoreError("기기 인증 저장소를 읽을 수 없습니다.") from error
        if not isinstance(data, dict) or not isinstance(data.get("devices"), dict) or not isinstance(data.get("conversations"), dict):
            raise DeviceStoreError("기기 인증 저장소의 형식이 올바르지 않습니다.")
        return data

    def _write(self, data: dict) -> None:
        temporary_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".devices-", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(data, temporary, ensure_ascii=False)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise DeviceStoreError("기기 인증 저장소를 저장할 수 없습니다.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue_device(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            data = self._read()
            data["devices"][self._token_hash(token)] = True
            self._write(data)
        return token

    def authenticate(self, token: str) -> str | None:
        if not isinstance(token, str) or not token or len(token) > 256:
            return None
        digest = self._token_hash(token)
        with self._lock:
            return digest if self._read()["devices"].get(digest) is True else None

    def register_conversation(self, owner: str, conversation_id: str) -> None:
        with self._lock:
            data = self._read()
            if data["devices"].get(owner) is not True or conversation_id in data["conversations"]:
                raise ConversationOwnershipError("통화를 등록할 수 없습니다.")
            data["conversations"][conversation_id] = owner
            self._write(data)

    def require_owner(self, owner: str, conversation_id: str) -> None:
        with self._lock:
            data = self._read()
            if data["devices"].get(owner) is not True or data["conversations"].get(conversation_id) != owner:
                raise ConversationOwnershipError("통화에 접근할 수 없습니다.")
