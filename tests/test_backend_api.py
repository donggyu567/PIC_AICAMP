"""HTTP contract tests for the FastAPI application."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app


class FakeCorrectionClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        del system_prompt
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider details must stay private")
        masked_text = json.loads(user_prompt.splitlines()[-1])["masked_text"]
        return json.dumps(
            {
                "tuned_text": masked_text + ".",
                "unclear_segments": [],
            },
            ensure_ascii=False,
        )


def payload(utterance_id: int = 1) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "conversation_id": "20260828_1430",
        "utterance_id": utterance_id,
        "masked_text": f"API 테스트 {utterance_id}",
        "has_masked_data": False,
        "masked_types": [],
    }


class BackendApiTests(unittest.TestCase):
    def test_post_duplicate_get_and_health(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeCorrectionClient()
            app = create_app(
                settings=Settings(data_root=Path(directory)),
                llm_client=client,
            )
            with TestClient(app) as api:
                health = api.get("/health")
                created = api.post("/api/v1/utterances", json=payload())
                duplicate = api.post("/api/v1/utterances", json=payload())
                latest = api.get(
                    "/api/v1/conversations/20260828_1430/context"
                )

            self.assertEqual(200, health.status_code)
            self.assertEqual({"status": "ok"}, health.json())
            self.assertEqual(201, created.status_code)
            self.assertEqual("created", created.json()["status"])
            self.assertEqual(200, duplicate.status_code)
            self.assertEqual("cached", duplicate.json()["status"])
            self.assertEqual(200, latest.status_code)
            self.assertEqual(1, latest.json()["context"]["current"]["utterance_id"])
            self.assertEqual(1, client.calls)
            self.assertTrue(created.headers["X-Request-ID"])

    def test_rejects_raw_text_and_invalid_mask_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeCorrectionClient()
            app = create_app(
                settings=Settings(data_root=Path(directory)),
                llm_client=client,
            )
            invalid_shape = payload()
            invalid_shape["raw_text"] = "노출 금지"
            invalid_contract = payload()
            invalid_contract["masked_text"] = "[PERSON]님"

            with TestClient(app) as api:
                shape_response = api.post(
                    "/api/v1/utterances",
                    json=invalid_shape,
                )
                contract_response = api.post(
                    "/api/v1/utterances",
                    json=invalid_contract,
                )

            self.assertEqual(422, shape_response.status_code)
            self.assertEqual(
                "INVALID_REQUEST",
                shape_response.json()["error"]["code"],
            )
            self.assertEqual(422, contract_response.status_code)
            self.assertEqual(
                "INVALID_MASKED_TRANSCRIPT",
                contract_response.json()["error"]["code"],
            )
            self.assertEqual(0, client.calls)
            self.assertNotIn("노출 금지", shape_response.text)

    def test_maps_provider_failure_to_safe_502(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(
                settings=Settings(data_root=Path(directory)),
                llm_client=FakeCorrectionClient(fail=True),
            )
            with TestClient(app) as api:
                response = api.post("/api/v1/utterances", json=payload())

            self.assertEqual(502, response.status_code)
            self.assertEqual(
                "CORRECTION_PROVIDER_ERROR",
                response.json()["error"]["code"],
            )
            self.assertNotIn("provider details", response.text)


if __name__ == "__main__":
    unittest.main()
