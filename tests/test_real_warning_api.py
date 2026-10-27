"""실제 경고 구현체와 서버의 계산·저장 연결을 검증한다."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import analysis_service
from backend.services.risk_service import ALLOWED_RISK_TYPES
from backend.stores.analysis_file_store import AnalysisFileStore
from models.warning_manager.warning_manager import DefaultWarningManager


def make_payload(number: int, score: float | None) -> dict:
    success = score is not None

    return {
        "conversation_id": "real-warning-test",
        "utterance_id": number,
        "revision": 1,
        "sequence": number,
        "tuned_text": f"테스트 발화 {number}",
        "analysis_status": "ok" if success else "error",
        "is_phishing_score": score,
        "type_scores": (
            {
                name: 0.8 if name == "money_transfer" else 0.0
                for name in ALLOWED_RISK_TYPES
            }
            if success
            else None
        ),
        "detected_types": ["money_transfer"] if success else None,
        "model_version": "fixed-test-v1",
    }


class RealWarningApiTests(unittest.TestCase):
    path = "/api/v1/dev/model-results"

    def setUp(self):
        # 테스트마다 별도의 저장 폴더를 만든다.
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.store = AnalysisFileStore(Path(directory))

        self.enterContext(
            patch.object(analysis_service, "analysis_store", self.store)
        )
        self.enterContext(
            patch.dict(os.environ, {"PIC_AI_MODE": "disabled"})
        )

        # 컨텍스트에 진입해야 lifespan이 실행된다.
        self.client = self.enterContext(TestClient(app))

    def post_result(self, number: int, score: float | None) -> dict:
        response = self.client.post(
            self.path,
            json=make_payload(number, score),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_startup_registers_real_warning_manager(self):
        self.assertIsInstance(
            app.state.warning_manager,
            DefaultWarningManager,
        )

        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "status": "not_ready",
                "ai_ready": False,
                "warning_ready": True,
                "ai_mode": "disabled",
                "model_version": None,
            },
        )

    def test_cumulative_warning_is_saved_and_retrieved(self):
        first = self.post_result(1, 0.55)

        self.assertEqual(first["warning"]["status"], "none")
        self.assertAlmostEqual(first["cumulative_risk_score"], 55.0)

        second = self.post_result(2, 0.55)

        self.assertAlmostEqual(second["current_risk_score"], 55.0)
        self.assertAlmostEqual(second["cumulative_risk_score"], 73.75)
        self.assertEqual(second["warning"]["status"], "active")
        self.assertEqual(second["warning"]["reason"], "cumulative")
        self.assertTrue(second["warning"]["message"].strip())
        self.assertEqual(
            second["evidence"]["cumulative_events"][0]["trigger_utterance_id"],
            2,
        )

        snapshot = self.store.load("real-warning-test")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.warning_state.status, "active")
        self.assertEqual(len(snapshot.warning_state.events), 1)
        self.assertEqual(
            snapshot.pending_notification_ids,
            [snapshot.warning_state.events[0].event_id],
        )

        fetched = self.client.get(
            self.path,
            params={"conversation_id": "real-warning-test"},
        )

        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json(), second)

    def test_analysis_failure_preserves_warning_and_evidence(self):
        self.post_result(1, 0.55)
        successful = self.post_result(2, 0.55)
        before = self.store.load("real-warning-test")

        failed = self.post_result(3, None)

        self.assertEqual(failed["analysis_status"], "error")
        self.assertIsNone(failed["current_risk_score"])
        self.assertIsNone(failed["cumulative_risk_score"])
        self.assertEqual(failed["warning"]["status"], "active")
        self.assertEqual(failed["evidence"], successful["evidence"])

        after = self.store.load("real-warning-test")

        self.assertEqual(after.warning_state, before.warning_state)
        self.assertEqual(
            after.pending_notification_ids,
            before.pending_notification_ids,
        )

        # 실패를 복구하기 전에는 다음 발화를 처리할 수 없다.
        blocked = self.client.post(
            self.path,
            json=make_payload(4, 0.1),
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)


if __name__ == "__main__":
    unittest.main()
