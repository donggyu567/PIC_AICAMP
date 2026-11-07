"""기기별 인증 토큰과 통화 소유 관계의 기본 동작."""

import tempfile
import unittest
from pathlib import Path

from server.security.device_store import ConversationOwnershipError, DeviceStore, DeviceStoreError


class DeviceStoreTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "devices.json"
        self.store = DeviceStore(self.path)

    def test_device_tokens_and_ownership_survive_restart(self):
        token = self.store.issue_device()
        other_token = self.store.issue_device()
        owner = self.store.authenticate(token)
        other = self.store.authenticate(other_token)
        self.assertIsNotNone(owner)
        self.assertNotEqual(owner, other)
        self.assertNotIn(token, self.path.read_text(encoding="utf-8"))
        self.store.register_conversation(owner, "call-1")
        restarted = DeviceStore(self.path)
        restarted.require_owner(restarted.authenticate(token), "call-1")
        self.assertIsNone(restarted.authenticate("invalid"))
        with self.assertRaises(ConversationOwnershipError):
            restarted.require_owner(other, "call-1")
        with self.assertRaises(ConversationOwnershipError):
            restarted.register_conversation(other, "call-1")

    def test_corrupt_storage_does_not_authenticate(self):
        self.path.write_text("not-json", encoding="utf-8")
        with self.assertRaises(DeviceStoreError):
            self.store.authenticate("any-token")


if __name__ == "__main__":
    unittest.main()
