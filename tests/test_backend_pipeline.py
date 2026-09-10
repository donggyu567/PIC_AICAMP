"""Integration tests for the file-backed correction pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.config import Settings
from backend.dependencies import build_services
from backend.errors import ConversationConflictError, RequestContractError


class FakeCorrectionClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        del system_prompt
        self.calls += 1
        masked_text = json.loads(user_prompt.splitlines()[-1])["masked_text"]
        return json.dumps(
            {
                "tuned_text": masked_text + ".",
                "unclear_segments": [],
            },
            ensure_ascii=False,
        )


def masked_payload(
    utterance_id: int,
    *,
    masked_text: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "conversation_id": "20260828_1430",
        "utterance_id": utterance_id,
        "masked_text": masked_text or f"테스트 발화 {utterance_id}",
        "has_masked_data": False,
        "masked_types": [],
    }


class CorrectionPipelineTests(unittest.TestCase):
    def test_processes_stores_and_reuses_duplicate_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeCorrectionClient()
            settings = Settings(data_root=Path(directory))
            pipeline = build_services(settings, llm_client=client).pipeline

            first = pipeline.process(masked_payload(1))
            second = pipeline.process(masked_payload(2))
            duplicate = pipeline.process(masked_payload(1))

            self.assertEqual("created", first.status)
            self.assertEqual("created", second.status)
            self.assertEqual("cached", duplicate.status)
            self.assertEqual(2, client.calls)
            self.assertEqual(2, second.context.current.utterance_id)
            self.assertEqual(
                [1],
                [item.utterance_id for item in second.context.history],
            )
            self.assertEqual(1, duplicate.context.current.utterance_id)
            self.assertTrue(first.context_path.is_file())
            self.assertEqual(
                "contexts/" + first.context_path.parent.name + "/context_result0001.json",
                first.storage_key,
            )

            correction_files = list(settings.corrections_root.rglob("*.json"))
            context_files = list(settings.contexts_root.rglob("*.json"))
            self.assertEqual(2, len(correction_files))
            self.assertEqual(2, len(context_files))
            self.assertNotIn(
                "raw_text",
                first.context_path.read_text(encoding="utf-8"),
            )

    def test_rebuilds_context_from_files_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(data_root=Path(directory), history_size=5)
            first_client = FakeCorrectionClient()
            first_pipeline = build_services(
                settings,
                llm_client=first_client,
            ).pipeline
            first_pipeline.process(masked_payload(1))
            first_pipeline.process(masked_payload(2))

            restarted_client = FakeCorrectionClient()
            restarted_pipeline = build_services(
                settings,
                llm_client=restarted_client,
            ).pipeline
            third = restarted_pipeline.process(masked_payload(3))

            self.assertEqual(1, restarted_client.calls)
            self.assertEqual(3, third.context.current.utterance_id)
            self.assertEqual(
                [1, 2],
                [item.utterance_id for item in third.context.history],
            )

    def test_retains_only_configured_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(data_root=Path(directory), history_size=5)
            pipeline = build_services(
                settings,
                llm_client=FakeCorrectionClient(),
            ).pipeline

            latest = None
            for utterance_id in range(1, 8):
                latest = pipeline.process(masked_payload(utterance_id))

            assert latest is not None
            self.assertEqual(7, latest.context.current.utterance_id)
            self.assertEqual(
                [2, 3, 4, 5, 6],
                [item.utterance_id for item in latest.context.history],
            )

    def test_rejects_conflicting_duplicate_and_out_of_order_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = build_services(
                Settings(data_root=Path(directory)),
                llm_client=FakeCorrectionClient(),
            ).pipeline
            pipeline.process(masked_payload(1))

            with self.assertRaises(ConversationConflictError):
                pipeline.process(masked_payload(1, masked_text="다른 발화"))
            with self.assertRaises(ConversationConflictError):
                pipeline.process(masked_payload(3))

    def test_rejects_raw_text_before_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeCorrectionClient()
            pipeline = build_services(
                Settings(data_root=Path(directory)),
                llm_client=client,
            ).pipeline
            payload = masked_payload(1)
            payload["raw_text"] = "서버에 보내면 안 되는 원문"

            with self.assertRaises(RequestContractError):
                pipeline.process(payload)
            self.assertEqual(0, client.calls)


if __name__ == "__main__":
    unittest.main()
