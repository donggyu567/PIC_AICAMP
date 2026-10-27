"""경고 알림의 저장·조회·수신확인을 외부 API 없이 검증한다."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import analysis_service
from backend.stores.analysis_file_store import AnalysisFileStore
from models.warning_manager.warning_manager import DefaultWarningManager
from tests.api_helpers import StubWarningManager, payload


class NotificationApiTests(unittest.TestCase):
    result_path = "/api/v1/dev/model-results"
    notification_path = "/api/v1/notifications"

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = AnalysisFileStore(Path(directory))
        self.enterContext(patch.object(analysis_service, "analysis_store", self.store))
        self.enterContext(patch.object(
            app.state, "warning_manager", DefaultWarningManager(), create=True,
        ))
        self.enterContext(patch.object(app.state, "risk_analyzer", None, create=True))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def post_result(self, number=1, score=0.8, conversation_id="api-test"):
        response = self.client.post(
            self.result_path, json=payload(number, score, conversation_id),
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def pending(self, conversation_id="api-test"):
        return self.client.get(
            self.notification_path, params={"conversation_id": conversation_id},
        )

    def ack(self, event_id, conversation_id="api-test"):
        return self.client.post(
            self.notification_path + "/ack",
            json={"conversation_id": conversation_id, "event_id": event_id},
        )

    def end(self, conversation_id="api-test"):
        return self.client.post(
            "/api/v1/conversations/end", json={"conversation_id": conversation_id},
        )

    def test_queries_repeat_first_event_payload_without_acknowledging(self):
        initial = self.post_result()
        first = self.pending()
        self.assertEqual(200, first.status_code, first.text)
        data = first.json()
        self.assertEqual("active", data["conversation_status"])
        self.assertEqual("api-test", data["conversation_id"])
        self.assertEqual(1, len(data["notifications"]))
        record = data["notifications"][0]
        self.assertEqual(initial["warning"], record["warning"])
        self.assertEqual(initial["evidence"], record["evidence"])
        self.assertEqual("pending", record["status"])
        self.assertIsNone(record["acknowledged_at"])
        self.assertIsNone(record["expired_at"])
        self.assertEqual(
            timezone.utc.utcoffset(None),
            datetime.fromisoformat(record["created_at"]).utcoffset(),
        )
        # 경고가 유지되며 근거가 바뀌어도 알림은 최초 발생 내용을 유지한다.
        latest = self.post_result(2, 0.95)
        self.assertNotEqual(initial["evidence"], latest["evidence"])
        self.assertEqual(data, self.pending().json())
        with patch.object(self.store, "save", side_effect=AssertionError("query must not save")):
            self.assertEqual(data, self.pending().json())

    def test_ack_is_idempotent_and_survives_storage_restart(self):
        self.post_result()
        original = self.pending().json()["notifications"][0]
        acknowledged = self.ack(original["event_id"])
        self.assertEqual(200, acknowledged.status_code, acknowledged.text)
        data = acknowledged.json()
        self.assertEqual("acknowledged", data["status"])
        self.assertIsNotNone(data["acknowledged_at"])
        self.assertEqual(original["created_at"], data["created_at"])
        self.assertEqual(original["warning"], data["warning"])
        self.assertEqual([], self.pending().json()["notifications"])
        self.assertEqual([], self.store.load("api-test").pending_notification_ids)
        restarted = AnalysisFileStore(self.store.root)
        with patch.object(analysis_service, "analysis_store", restarted):
            self.assertEqual([], self.pending().json()["notifications"])
            with patch.object(restarted, "save", side_effect=AssertionError("repeat must not save")):
                self.assertEqual(data, self.ack(original["event_id"]).json())

    def test_pending_survives_restart_until_app_acknowledges(self):
        self.post_result()
        original = self.pending().json()
        with patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)):
            self.assertEqual(original, self.pending().json())

    def test_acknowledged_event_id_is_not_reenqueued(self):
        # 잘못 반복 반환된 notify_event_id도 이미 확인한 알림을 재생성하지 않는다.
        manager = StubWarningManager()
        with patch.object(app.state, "warning_manager", manager):
            self.post_result()
            record = self.pending().json()["notifications"][0]
            self.assertEqual(200, self.ack(record["event_id"]).status_code)
            self.post_result(2, 0.9)
        self.assertEqual([], self.pending().json()["notifications"])
        snapshot = self.store.load("api-test")
        self.assertEqual(1, len(snapshot.notifications))
        self.assertEqual("acknowledged", snapshot.notifications[0].status)

    def test_no_alert_for_safe_or_failed_analysis_and_failure_keeps_existing_alert(self):
        self.post_result(score=0.1)
        self.assertEqual([], self.pending().json()["notifications"])
        self.post_result(2, None)
        self.assertEqual([], self.pending().json()["notifications"])
        self.post_result(conversation_id="warning-call")
        original = self.pending("warning-call").json()
        self.post_result(2, None, "warning-call")
        self.assertEqual(original, self.pending("warning-call").json())

    def test_later_warning_event_has_its_own_notification_and_ack(self):
        first = self.post_result()
        first_record = self.pending().json()["notifications"][0]
        # 첫 위험 발화가 최근 20개 창을 벗어난 뒤 다시 경고가 발생한다.
        for number in range(2, 22):
            last = self.post_result(number, 0.0)
        self.assertEqual("previous_warning", last["warning"]["status"])
        second = self.post_result(22, 0.9)
        records = self.pending().json()["notifications"]
        self.assertEqual(2, len(records))
        self.assertNotEqual(records[0]["event_id"], records[1]["event_id"])
        self.assertEqual(first["evidence"], records[0]["evidence"])
        self.assertEqual(second["evidence"], records[1]["evidence"])
        self.assertEqual(200, self.ack(first_record["event_id"]).status_code)
        self.assertEqual([records[1]], self.pending().json()["notifications"])

    def test_retry_of_failed_analysis_creates_notification_only_after_success(self):
        self.post_result(score=None)
        self.assertEqual([], self.pending().json()["notifications"])
        response = self.client.post(self.result_path + "/retry", json=payload(score=0.8))
        self.assertEqual(200, response.status_code, response.text)
        records = self.pending().json()["notifications"]
        self.assertEqual(1, len(records))
        self.assertEqual(response.json()["warning"], records[0]["warning"])
        self.assertEqual(1, len(self.store.load("api-test").records[0].previous_attempts))

    def test_end_expires_pending_alert_and_late_ack_preserves_expiration(self):
        self.post_result()
        record = self.pending().json()["notifications"][0]
        ended = self.end()
        self.assertEqual(200, ended.status_code, ended.text)
        self.assertEqual(
            {"conversation_id": "api-test", "conversation_status": "ended", "notifications": []},
            self.pending().json(),
        )
        snapshot = self.store.load("api-test")
        self.assertEqual([], snapshot.pending_notification_ids)
        expired = snapshot.notifications[0]
        self.assertEqual("expired", expired.status)
        self.assertEqual(snapshot.ended_at, expired.expired_at)
        self.assertIsNone(expired.acknowledged_at)
        self.assertEqual(record["evidence"], expired.evidence)
        with patch.object(self.store, "save", side_effect=AssertionError("expired ACK must not save")):
            late_ack = self.ack(record["event_id"])
        self.assertEqual(200, late_ack.status_code, late_ack.text)
        self.assertEqual(expired.model_dump(mode="json"), late_ack.json())

    def test_end_does_not_expire_already_acknowledged_alert(self):
        self.post_result()
        event_id = self.pending().json()["notifications"][0]["event_id"]
        acknowledged = self.ack(event_id).json()
        self.assertEqual(200, self.end().status_code)
        self.assertEqual(acknowledged, self.ack(event_id).json())

    def test_failed_ack_save_preserves_pending_and_can_be_retried(self):
        self.post_result()
        record = self.pending().json()["notifications"][0]
        path = self.store.path_for("api-test")
        before = path.read_text(encoding="utf-8")
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            self.assertEqual(503, self.ack(record["event_id"]).status_code)
        self.assertEqual(before, path.read_text(encoding="utf-8"))
        self.assertEqual([record], self.pending().json()["notifications"])
        self.assertEqual([], list(self.store.root.glob(".analysis-*.tmp")))
        self.assertEqual(200, self.ack(record["event_id"]).status_code)

    def test_failed_analysis_save_does_not_leave_notification_without_analysis(self):
        self.post_result(score=0.1)
        path = self.store.path_for("api-test")
        before = path.read_text(encoding="utf-8")
        with patch("backend.stores.analysis_file_store.os.replace", side_effect=OSError("disk")):
            response = self.client.post(self.result_path, json=payload(2, 0.9))
        self.assertEqual(503, response.status_code, response.text)
        self.assertEqual(before, path.read_text(encoding="utf-8"))
        self.assertEqual([], self.pending().json()["notifications"])
        self.post_result(2, 0.9)
        self.assertEqual(1, len(self.pending().json()["notifications"]))

    def test_missing_invalid_and_cross_conversation_requests_do_not_modify_storage(self):
        self.assertEqual(404, self.pending().status_code)
        self.assertEqual(404, self.ack("missing").status_code)
        self.assertEqual(422, self.client.get(self.notification_path).status_code)
        for conversation_id in ("", "   ", "x" * 121):
            with self.subTest(conversation_id=conversation_id):
                self.assertEqual(422, self.pending(conversation_id).status_code)
        invalid_bodies = (
            {}, {"conversation_id": "api-test"},
            {"conversation_id": "api-test", "event_id": ""},
            {"conversation_id": "api-test", "event_id": "  "},
            {"conversation_id": "api-test", "event_id": "x" * 201},
            {"conversation_id": "api-test", "event_id": 12},
            {"conversation_id": "  ", "event_id": "event"},
            {"conversation_id": "api-test", "event_id": "event", "status": "acknowledged"},
        )
        for body in invalid_bodies:
            with self.subTest(body=body):
                self.assertEqual(422, self.client.post(
                    self.notification_path + "/ack", json=body,
                ).status_code)
        self.assertEqual([], list(self.store.root.iterdir()))
        self.post_result()
        self.post_result(conversation_id="other")
        event_id = self.pending().json()["notifications"][0]["event_id"]
        other_before = self.store.path_for("other").read_text(encoding="utf-8")
        self.assertEqual(404, self.ack(event_id, "other").status_code)
        self.assertEqual(404, self.ack("unknown-event").status_code)
        self.assertEqual(other_before, self.store.path_for("other").read_text(encoding="utf-8"))

    def test_corrupt_storage_returns_503_without_overwriting(self):
        path = self.store.path_for("api-test")
        path.write_text("broken-json", encoding="utf-8")
        self.assertEqual(503, self.pending().status_code)
        self.assertEqual(503, self.ack("event").status_code)
        self.assertEqual("broken-json", path.read_text(encoding="utf-8"))

    def test_legacy_pending_ids_migrate_using_original_trigger_response(self):
        trigger = self.post_result()
        self.post_result(2, 0.95)
        path = self.store.path_for("api-test")
        legacy = json.loads(path.read_text(encoding="utf-8"))
        legacy.pop("notifications")
        legacy.pop("final_warning_result", None)
        path.write_text(json.dumps(legacy), encoding="utf-8")
        response = self.pending()
        self.assertEqual(200, response.status_code, response.text)
        record = response.json()["notifications"][0]
        self.assertIsNone(record["created_at"])
        self.assertEqual(trigger["warning"], record["warning"])
        self.assertEqual(trigger["evidence"], record["evidence"])
        self.assertEqual(200, self.ack(record["event_id"]).status_code)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("acknowledged", saved["notifications"][0]["status"])

    def test_legacy_ended_call_never_exposes_stale_pending_alert(self):
        self.post_result()
        path = self.store.path_for("api-test")
        legacy = json.loads(path.read_text(encoding="utf-8"))
        legacy.pop("notifications")
        legacy.pop("final_warning_result", None)
        legacy["conversation_status"] = "ended"
        legacy["ended_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(legacy), encoding="utf-8")
        response = self.pending()
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([], response.json()["notifications"])
        snapshot = self.store.load("api-test")
        self.assertEqual("expired", snapshot.notifications[0].status)
        self.assertEqual(snapshot.ended_at, snapshot.notifications[0].expired_at)
        self.assertEqual([], snapshot.pending_notification_ids)

    def test_concurrent_ack_and_end_preserve_history_and_a_terminal_notification_state(self):
        self.post_result()
        record = self.pending().json()["notifications"][0]
        before = self.store.load("api-test")
        with ThreadPoolExecutor(max_workers=2) as pool:
            ack_future = pool.submit(self.ack, record["event_id"])
            end_future = pool.submit(self.end)
            acknowledged, ended = ack_future.result(), end_future.result()
        self.assertEqual(200, acknowledged.status_code, acknowledged.text)
        self.assertEqual(200, ended.status_code, ended.text)
        after = self.store.load("api-test")
        self.assertEqual("ended", after.conversation_status)
        self.assertEqual(before.records, after.records)
        self.assertEqual([], after.pending_notification_ids)
        self.assertEqual(1, len(after.notifications))
        self.assertIn(after.notifications[0].status, ("acknowledged", "expired"))
        self.assertEqual([], self.pending().json()["notifications"])


if __name__ == "__main__":
    unittest.main()
