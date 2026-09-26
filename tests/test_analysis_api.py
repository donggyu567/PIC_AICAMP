"""파일 기반 분석 API 검증. 임시 폴더를 사용하고 외부 AI를 호출하지 않는다."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import analysis_service
from backend.services.risk_service import ALLOWED_RISK_TYPES
from backend.stores.analysis_file_store import AnalysisFileStore


def payload(sequence=1, score=0.55, conversation_id="api-test"):
    return {
        "conversation_id": conversation_id,
        "utterance_id": sequence,
        "revision": 1,
        "sequence": sequence,
        "tuned_text": "계산 확인용 문장입니다.",
        "analysis_status": "ok" if score is not None else "error",
        "is_phishing_score": score,
        "type_scores": (
            {name: 0.2 for name in ALLOWED_RISK_TYPES}
            if score is not None else None
        ),
        "detected_types": [] if score is not None else None,
        "model_version": "sample-v1",
    }


class AnalysisApiTests(unittest.TestCase):
    path = "/api/v1/dev/model-results"
    retry_path = "/api/v1/dev/model-results/retry"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = AnalysisFileStore(Path(self.directory.name))
        patcher = patch.object(analysis_service, "analysis_store", self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_sequential_calculation_and_conversation_isolation(self):
        first = self.client.post(self.path, json=payload())
        second = self.client.post(self.path, json=payload(2))
        other = self.client.post(self.path, json=payload(conversation_id="other"))
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual(200, other.status_code)
        self.assertAlmostEqual(55.0, first.json()["cumulative_risk_score"])
        self.assertAlmostEqual(73.75, second.json()["cumulative_risk_score"])
        self.assertAlmostEqual(55.0, other.json()["cumulative_risk_score"])
        self.assertEqual([], first.json()["detected_types"])
        self.assertEqual({20.0}, set(first.json()["type_scores"].values()))

    def test_window_excludes_first_utterance_at_sequence_21(self):
        for sequence in range(1, 22):
            response = self.client.post(
                self.path,
                json=payload(sequence, 0.92 if sequence == 1 else 0.05),
            )
            self.assertEqual(200, response.status_code)
            if sequence == 20:
                self.assertAlmostEqual(92.0, response.json()["cumulative_risk_score"])
        result = response.json()
        self.assertAlmostEqual(5.0, result["cumulative_risk_score"])
        self.assertEqual(list(range(2, 22)), result["calculation"]["window_utterance_ids"])

    def test_duplicate_and_gap_do_not_change_stored_history(self):
        self.assertEqual(200, self.client.post(self.path, json=payload()).status_code)
        self.assertEqual(409, self.client.post(self.path, json=payload()).status_code)
        self.assertEqual(409, self.client.post(self.path, json=payload(3)).status_code)
        self.assertEqual(1, len(self.store.get_history("api-test")))
        second = self.client.post(self.path, json=payload(2))
        self.assertEqual(200, second.status_code)
        self.assertAlmostEqual(73.75, second.json()["cumulative_risk_score"])

    def test_failed_analysis_returns_null_and_blocks_following_results(self):
        self.client.post(self.path, json=payload())
        failed = self.client.post(self.path, json=payload(2, None))
        self.assertEqual(200, failed.status_code)
        self.assertEqual("error", failed.json()["analysis_status"])
        for field in (
            "current_risk_score", "cumulative_risk_score", "type_scores",
            "detected_types", "calculation",
        ):
            self.assertIsNone(failed.json()[field])
        blocked = self.client.post(self.path, json=payload(3))
        self.assertEqual(409, blocked.status_code)
        history = self.store.get_history("api-test")
        self.assertEqual(2, len(history))
        self.assertEqual(0.55, history[0].is_phishing_score)
        self.assertEqual("error", history[1].analysis_status)

    def test_first_failure_is_also_recorded(self):
        response = self.client.post(self.path, json=payload(1, None))
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()["cumulative_risk_score"])
        self.assertEqual(1, len(self.store.get_history("api-test")))

    def test_invalid_contracts_return_422_without_saving(self):
        invalid = []
        for score in (1.1, -0.1, True, "0.55"):
            invalid.append({**payload(), "is_phishing_score": score})
        invalid.extend([
            {**payload(), "type_scores": {}},
            {**payload(), "type_scores": {**payload()["type_scores"], "unknown": 0.0}},
            {**payload(), "analysis_status": "error"},
            {**payload(), "detected_types": ["secrecy", "secrecy"]},
            {**payload(), "conversation_id": " "},
            {**payload(), "revision": 2},
            {**payload(), "raw_text": "허용되지 않는 필드"},
        ])
        for item in invalid:
            with self.subTest(item=item):
                response = self.client.post(self.path, json=item)
                self.assertEqual(422, response.status_code, response.text)
                self.assertEqual([], self.store.get_history("api-test"))

    def test_swagger_example_is_valid_and_health_remains_available(self):
        schema = self.client.get("/openapi.json").json()
        example = schema["components"]["schemas"]["ModelResultRequest"]["example"]
        self.assertEqual(200, self.client.post(self.path, json=example).status_code)
        self.assertEqual({"status": "ok"}, self.client.get("/health").json())

    def test_stored_json_and_latest_or_specific_lookup(self):
        first = self.client.post(self.path, json=payload()).json()
        second = self.client.post(self.path, json=payload(2)).json()
        latest = self.client.get(self.path, params={"conversation_id": "api-test"})
        previous = self.client.get(
            self.path, params={"conversation_id": "api-test", "utterance_id": 1},
        )
        self.assertEqual(second, latest.json())
        self.assertEqual(first, previous.json())
        stored = json.loads(self.store.path_for("api-test").read_text(encoding="utf-8"))
        self.assertEqual(2, len(stored["records"]))
        self.assertEqual(second, stored["records"][-1]["response"])
        self.assertEqual(0.55, stored["records"][0]["model_result"]["is_phishing_score"])
        for params in (
            {"conversation_id": "missing"},
            {"conversation_id": "api-test", "utterance_id": 99},
        ):
            self.assertEqual(404, self.client.get(self.path, params=params).status_code)

    def test_restart_restores_history_and_original_policy(self):
        self.client.post(self.path, json=payload())
        restarted = AnalysisFileStore(Path(self.directory.name))
        with (
            patch.object(analysis_service, "analysis_store", restarted),
            patch.object(analysis_service, "RHO", 0.5),
            patch.object(analysis_service, "POLICY_VERSION", "new-policy"),
        ):
            second = self.client.post(self.path, json=payload(2))
            duplicate = self.client.post(self.path, json=payload())
        self.assertEqual(200, second.status_code)
        self.assertAlmostEqual(73.75, second.json()["cumulative_risk_score"])
        self.assertEqual(0.95, second.json()["calculation"]["rho"])
        self.assertEqual("risk-policy-v1", second.json()["calculation"]["policy_version"])
        self.assertEqual(409, duplicate.status_code)

    def test_restart_retains_failure_and_blocks_following_results(self):
        failed = self.client.post(self.path, json=payload(1, None)).json()
        with patch.object(
            analysis_service, "analysis_store", AnalysisFileStore(Path(self.directory.name))
        ):
            restored = self.client.get(self.path, params={"conversation_id": "api-test"})
            blocked = self.client.post(self.path, json=payload(2))
        self.assertEqual(failed, restored.json())
        self.assertEqual(409, blocked.status_code)

    def test_replace_failure_keeps_previous_file_and_allows_retry(self):
        self.client.post(self.path, json=payload())
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        with patch(
            "backend.stores.analysis_file_store.os.replace",
            side_effect=OSError("private filesystem detail"),
        ):
            response = self.client.post(self.path, json=payload(2))
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private filesystem detail", response.text)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))
        self.assertEqual([], list(self.store.root.glob("*.tmp")))
        retry = self.client.post(self.path, json=payload(2))
        self.assertEqual(200, retry.status_code)
        self.assertAlmostEqual(73.75, retry.json()["cumulative_risk_score"])

    def test_corrupt_file_is_not_treated_as_empty_or_overwritten(self):
        self.client.post(self.path, json=payload())
        path = self.store.path_for("api-test")
        path.write_text('{"broken":', encoding="utf-8")
        self.assertEqual(503, self.client.post(self.path, json=payload(2)).status_code)
        response = self.client.get(self.path, params={"conversation_id": "api-test"})
        self.assertEqual(503, response.status_code)
        self.assertEqual('{"broken":', path.read_text(encoding="utf-8"))

    def test_input_response_mismatch_is_rejected(self):
        self.client.post(self.path, json=payload())
        path = self.store.path_for("api-test")
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["records"][0]["response"]["current_risk_score"] = 0.0
        path.write_text(json.dumps(stored), encoding="utf-8")
        self.assertEqual(503, self.client.post(self.path, json=payload(2)).status_code)

    def test_conversation_id_cannot_escape_storage_directory(self):
        conversation_id = "../../outside/CON"
        response = self.client.post(self.path, json=payload(conversation_id=conversation_id))
        self.assertEqual(200, response.status_code)
        path = self.store.path_for(conversation_id)
        self.assertEqual(self.store.root, path.parent)
        self.assertRegex(path.name, r"^[0-9a-f]{64}\.json$")
        self.assertEqual(1, len(list(self.store.root.iterdir())))
        restored = self.client.get(self.path, params={"conversation_id": conversation_id})
        self.assertEqual(response.json(), restored.json())

    def test_concurrent_duplicate_requests_commit_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(
                lambda _: self.client.post(self.path, json=payload()).status_code,
                range(4),
            ))
        self.assertEqual([200, 409, 409, 409], sorted(statuses))
        self.assertEqual(1, len(self.store.get_history("api-test")))

    def test_retry_recovers_failed_utterance_and_allows_next(self):
        self.client.post(self.path, json=payload())
        failed = self.client.post(self.path, json=payload(2, None)).json()
        self.assertEqual(409, self.client.post(self.path, json=payload(3)).status_code)
        recovered = self.client.post(self.retry_path, json=payload(2))
        self.assertEqual(200, recovered.status_code)
        self.assertAlmostEqual(73.75, recovered.json()["cumulative_risk_score"])
        stored = self.store.load("api-test")
        self.assertEqual(2, len(stored.records))
        self.assertEqual(1, len(stored.records[-1].previous_attempts))
        self.assertEqual(failed, stored.records[-1].previous_attempts[0].response.model_dump())
        latest = self.client.get(self.path, params={"conversation_id": "api-test"})
        self.assertEqual(recovered.json(), latest.json())
        self.assertEqual(200, self.client.post(self.path, json=payload(3)).status_code)
        self.assertEqual(3, len(self.store.load("api-test").records))

    def test_retry_failure_keeps_blocking_and_preserves_all_attempts(self):
        self.client.post(self.path, json=payload(1, None))
        failed_retry = self.client.post(
            self.retry_path, json={**payload(1, None), "model_version": "sample-v2"},
        )
        self.assertEqual(200, failed_retry.status_code)
        self.assertIsNone(failed_retry.json()["cumulative_risk_score"])
        self.assertEqual(409, self.client.post(self.path, json=payload(2)).status_code)
        recovered = self.client.post(
            self.retry_path, json={**payload(), "model_version": "sample-v3"},
        )
        self.assertEqual(200, recovered.status_code)
        self.assertAlmostEqual(55.0, recovered.json()["cumulative_risk_score"])
        record = self.store.load("api-test").records[0]
        self.assertEqual("sample-v3", record.model_result.model_version)
        self.assertEqual(
            ["sample-v1", "sample-v2"],
            [attempt.model_result.model_version for attempt in record.previous_attempts],
        )

    def test_retry_after_restart_uses_saved_policy_and_preserves_audit(self):
        self.client.post(self.path, json=payload())
        self.client.post(self.path, json=payload(2, None))
        with (
            patch.object(analysis_service, "analysis_store", AnalysisFileStore(self.store.root)),
            patch.object(analysis_service, "RHO", 0.5),
            patch.object(analysis_service, "POLICY_VERSION", "new-policy"),
        ):
            recovered = self.client.post(self.retry_path, json=payload(2))
        self.assertEqual(200, recovered.status_code)
        self.assertAlmostEqual(73.75, recovered.json()["cumulative_risk_score"])
        self.assertEqual(0.95, recovered.json()["calculation"]["rho"])
        snapshot = AnalysisFileStore(self.store.root).load("api-test")
        self.assertEqual("ok", snapshot.records[-1].model_result.analysis_status)
        self.assertEqual("error", snapshot.records[-1].previous_attempts[0].model_result.analysis_status)

    def test_retry_rejects_missing_successful_or_mismatched_targets(self):
        missing = self.client.post(self.retry_path, json=payload())
        self.assertEqual(404, missing.status_code)
        self.assertEqual([], list(self.store.root.iterdir()))
        self.client.post(self.path, json=payload())
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        self.assertEqual(409, self.client.post(self.retry_path, json=payload()).status_code)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))
        self.client.post(self.path, json=payload(2, None))
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        for item in (
            payload(), payload(3),
            {**payload(2), "utterance_id": 99},
            {**payload(2), "tuned_text": "수정된 문장입니다."},
        ):
            with self.subTest(item=item):
                self.assertEqual(409, self.client.post(self.retry_path, json=item).status_code)
                self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))
        for item in (
            {**payload(2), "revision": 2},
            {**payload(2), "is_phishing_score": 1.1},
            {**payload(2), "analysis_status": "error"},
        ):
            self.assertEqual(422, self.client.post(self.retry_path, json=item).status_code)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))

    def test_retry_write_failure_retains_failed_state_and_is_retryable(self):
        self.client.post(self.path, json=payload(1, None))
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        with patch(
            "backend.stores.analysis_file_store.os.replace",
            side_effect=OSError("private filesystem detail"),
        ):
            response = self.client.post(self.retry_path, json=payload())
        self.assertEqual(503, response.status_code)
        self.assertNotIn("private filesystem detail", response.text)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))
        self.assertEqual(409, self.client.post(self.path, json=payload(2)).status_code)
        self.assertEqual(200, self.client.post(self.retry_path, json=payload()).status_code)
        self.assertEqual(1, len(self.store.load("api-test").records[0].previous_attempts))

    def test_concurrent_successful_retries_commit_once(self):
        self.client.post(self.path, json=payload(1, None))
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(
                lambda _: self.client.post(self.retry_path, json=payload()).status_code,
                range(4),
            ))
        self.assertEqual([200, 409, 409, 409], sorted(statuses))
        self.assertEqual(1, len(self.store.load("api-test").records[0].previous_attempts))

    def test_old_snapshot_without_attempt_history_can_be_recovered(self):
        self.client.post(self.path, json=payload(1, None))
        path = self.store.path_for("api-test")
        stored = json.loads(path.read_text(encoding="utf-8"))
        del stored["records"][0]["previous_attempts"]
        path.write_text(json.dumps(stored), encoding="utf-8")
        response = self.client.post(self.retry_path, json=payload())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(self.store.load("api-test").records[0].previous_attempts))

    def test_corrupt_retry_history_is_rejected_without_overwriting(self):
        self.client.post(self.path, json=payload(1, None))
        self.client.post(self.retry_path, json=payload())
        path = self.store.path_for("api-test")
        stored = json.loads(path.read_text(encoding="utf-8"))
        attempt = stored["records"][0]["previous_attempts"][0]
        attempt["model_result"]["utterance_id"] = 99
        attempt["response"]["utterance_id"] = 99
        corrupted = json.dumps(stored)
        path.write_text(corrupted, encoding="utf-8")
        response = self.client.get(self.path, params={"conversation_id": "api-test"})
        self.assertEqual(503, response.status_code)
        self.assertEqual(corrupted, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
