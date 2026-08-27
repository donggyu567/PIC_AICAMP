"""Tests for recent conversation context management."""

from __future__ import annotations

import json
import unittest

from risk_speech_ai.context_manager import ConversationContextManager
from risk_speech_ai.schemas import ConversationContext, Utterance


def utterance(utterance_id: int, conversation_id: str = "C0001") -> Utterance:
    return Utterance(
        schema_version="1.0",
        conversation_id=conversation_id,
        utterance_id=utterance_id,
        masked_text=f"[이름] {utterance_id}",
        has_masked_data=True,
        masked_types=["PERSON"],
        tuned_text=f"[이름] {utterance_id}.",
        is_tuned=True,
        has_unclear=False,
        unclear_segments=[],
    )


def add_range(manager: ConversationContextManager, last_id: int) -> None:
    for utterance_id in range(1, last_id + 1):
        manager.add(utterance(utterance_id))


class ConversationContextManagerTests(unittest.TestCase):
    def test_one_utterance_has_empty_history(self) -> None:
        manager = ConversationContextManager()

        context = manager.add(utterance(1))

        self.assert_context_ids(context, current=1, history=[])

    def test_four_utterances_keep_first_three_as_history(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 4)

        self.assert_context_ids(manager.get_context(), current=4, history=[1, 2, 3])

    def test_five_utterances_keep_first_four_as_history(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 5)

        self.assert_context_ids(manager.get_context(), current=5, history=[1, 2, 3, 4])

    def test_six_utterances_keep_five_as_history(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 6)

        self.assert_context_ids(manager.get_context(), current=6, history=[1, 2, 3, 4, 5])

    def test_seven_utterances_drop_oldest_history(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 7)

        self.assert_context_ids(manager.get_context(), current=7, history=[2, 3, 4, 5, 6])

    def test_orders_out_of_order_input_by_utterance_id(self) -> None:
        manager = ConversationContextManager()
        for utterance_id in (3, 1, 2):
            manager.add(utterance(utterance_id))

        self.assert_context_ids(manager.get_context(), current=3, history=[1, 2])

    def test_rejects_duplicate_id_within_same_conversation(self) -> None:
        manager = ConversationContextManager()
        manager.add(utterance(1))

        with self.assertRaises(ValueError):
            manager.add(utterance(1))

    def test_allows_same_utterance_id_in_different_conversations(self) -> None:
        manager = ConversationContextManager()

        first_context = manager.add(utterance(1, "C0001"))
        second_context = manager.add(utterance(1, "C0002"))

        self.assertEqual("C0001", first_context.current.conversation_id)
        self.assertEqual("C0002", second_context.current.conversation_id)

    def test_does_not_mix_history_between_conversations(self) -> None:
        manager = ConversationContextManager()
        manager.add(utterance(1, "C0001"))
        manager.add(utterance(1, "C0002"))
        manager.add(utterance(2, "C0001"))

        context = manager.get_context("C0001")

        self.assert_context_ids(context, current=2, history=[1])
        self.assertTrue(
            all(item.conversation_id == "C0001" for item in context.history)
        )

    def test_configurable_history_size(self) -> None:
        manager = ConversationContextManager(history_size=3)
        add_range(manager, 6)

        self.assert_context_ids(manager.get_context(), current=6, history=[3, 4, 5])

    def test_context_converts_to_expected_dict_without_raw_text(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 4)

        payload = manager.get_context().to_dict()

        self.assertEqual(4, payload["current"]["utterance_id"])
        self.assertEqual("1.0", payload["current"]["schema_version"])
        self.assertEqual("C0001", payload["current"]["conversation_id"])
        self.assertEqual([1, 2, 3], [item["utterance_id"] for item in payload["history"]])
        self.assertTrue(
            all(item["schema_version"] == "1.0" for item in payload["history"])
        )
        self.assertTrue(
            all(item["conversation_id"] == "C0001" for item in payload["history"])
        )
        self.assertNotIn("raw_text", payload["current"])
        self.assertTrue(payload["current"]["has_masked_data"])
        self.assertEqual(["PERSON"], payload["current"]["masked_types"])
        json.dumps(payload)

    def assert_context_ids(
        self, context: ConversationContext, *, current: int, history: list[int]
    ) -> None:
        self.assertEqual(current, context.current.utterance_id)
        self.assertEqual(history, [item.utterance_id for item in context.history])
