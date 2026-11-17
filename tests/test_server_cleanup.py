"""서버 정리 후 통화 병렬성·계산 창·전체 기록 검증을 확인한다."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from backend.main import app
from backend.schemas import ModelResultRequest, UtteranceRequest
from backend.services import analysis_service, pipeline_service
from backend.stores.analysis_file_store import AnalysisFileStore, AnalysisStorageError
from backend.stores.analysis_store import AnalysisConflictError
from backend.stores.conversation_locks import ConversationLocks
from models.llm_correction import CorrectionEngine
from tests.api_helpers import StubCorrectionClient, StubRiskAnalyzer, payload, utterance


class ServerCleanupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = AnalysisFileStore(Path(directory.name))
        patcher = patch.object(analysis_service, "analysis_store", self.store)
        patcher.start()
        self.addCleanup(patcher.stop)

    def append(self, sequence, score=0.55):
        return analysis_service.process_model_result(
            ModelResultRequest.model_validate(payload(sequence, score))
        )

    def test_another_conversation_completes_while_first_correction_waits(self):
        started, release = Event(), Event()

        class BlockingClient(StubCorrectionClient):
            def complete(self, *, system_prompt, user_prompt):
                if json.loads(user_prompt.splitlines()[-1])["masked_text"] == "대기 문장":
                    started.set()
                    if not release.wait(10):
                        raise TimeoutError("test did not release correction")
                return super().complete(system_prompt=system_prompt, user_prompt=user_prompt)

        first = UtteranceRequest.model_validate({
            **utterance(conversation_id="waiting"), "masked_text": "대기 문장",
        })
        second = UtteranceRequest.model_validate(utterance(conversation_id="other"))
        analyzer = StubRiskAnalyzer()
        with patch.object(
            pipeline_service, "get_correction_engine",
            return_value=CorrectionEngine(BlockingClient()),
        ), ThreadPoolExecutor(max_workers=2) as pool:
            waiting = pool.submit(pipeline_service.analyze_utterance, first, analyzer)
            try:
                self.assertTrue(started.wait(3))
                other = pool.submit(pipeline_service.analyze_utterance, second, analyzer)
                self.assertEqual("other", other.result(timeout=3).conversation_id)
                self.assertFalse(waiting.done())
            finally:
                release.set()
            self.assertEqual("waiting", waiting.result(timeout=3).conversation_id)
        self.assertEqual(1, len(self.store.load("waiting").records))
        self.assertEqual(1, len(self.store.load("other").records))

    def test_retry_uses_last_twenty_and_preserves_older_records(self):
        for number in range(1, 25):
            self.append(number, 0.99 if number == 1 else 0.05)
        self.append(25, None)
        result = analysis_service.retry_model_result(
            ModelResultRequest.model_validate(payload(25, 0.05))
        )
        self.assertAlmostEqual(5.0, result.cumulative_risk_score)
        self.assertEqual(list(range(6, 26)), result.calculation.window_utterance_ids)
        snapshot = self.store.load("api-test")
        self.assertEqual(25, len(snapshot.records))
        self.assertAlmostEqual(99.0, snapshot.records[0].response.current_risk_score)
        self.assertEqual(1, len(snapshot.records[-1].previous_attempts))

    def test_window_size_one_excludes_all_previous_results(self):
        with patch.object(analysis_service, "WINDOW_SIZE", 1):
            self.append(1, 0.99)
        self.append(2, None)
        result = analysis_service.retry_model_result(
            ModelResultRequest.model_validate(payload(2, 0.05))
        )
        self.assertAlmostEqual(5.0, result.cumulative_risk_score)
        self.assertEqual([2], result.calculation.window_utterance_ids)
        self.assertEqual(1, result.calculation.window_size)

    def test_duplicate_id_outside_calculation_window_is_rejected(self):
        for number in range(1, 23):
            self.append(number)
        before = self.store.path_for("api-test").read_text(encoding="utf-8")
        duplicate = ModelResultRequest.model_validate({**payload(23), "utterance_id": 1})
        with self.assertRaises(AnalysisConflictError):
            analysis_service.process_model_result(duplicate)
        self.assertEqual(before, self.store.path_for("api-test").read_text(encoding="utf-8"))

    def test_corruption_outside_calculation_window_is_still_rejected(self):
        for number in range(1, 23):
            self.append(number)
        path = self.store.path_for("api-test")
        original = json.loads(path.read_text(encoding="utf-8"))
        for field, value in (("utterance_id", 1), ("sequence", 99)):
            with self.subTest(field=field):
                corrupted = json.loads(json.dumps(original))
                for key in ("model_result", "response"):
                    corrupted["records"][1][key][field] = value
                text = json.dumps(corrupted, ensure_ascii=False)
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(AnalysisStorageError):
                    self.append(23)
                self.assertEqual(text, path.read_text(encoding="utf-8"))

    def test_lock_cleanup_after_nested_use_and_failure(self):
        locks = ConversationLocks()
        with self.assertRaisesRegex(RuntimeError, "failed"):
            with locks.hold("call"), locks.hold("call"):
                raise RuntimeError("failed")
        # 통화 ID가 늘어나도 종료된 요청의 잠금을 계속 보관하지 않는다.
        self.assertEqual({}, locks._entries)
        with ThreadPoolExecutor(max_workers=1) as pool:
            def reuse():
                with locks.hold("call"):
                    return True
            self.assertTrue(pool.submit(reuse).result(timeout=3))
        self.assertEqual({}, locks._entries)

    def test_openapi_exposes_integrated_route_without_legacy_correction_route(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/utterances/analyze", paths)
        self.assertNotIn("/api/v1/utterances", paths)


if __name__ == "__main__":
    unittest.main()
