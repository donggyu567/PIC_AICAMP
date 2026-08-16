"""Tests for recent conversation context management."""

from __future__ import annotations

import json
import unittest

from risk_speech_ai.context_manager import ConversationContextManager
from risk_speech_ai.schemas import ConversationContext, Utterance


def utterance(utterance_id: int) -> Utterance:
    return Utterance(
        utterance_id=utterance_id,
        raw_text=f"원본 {utterance_id}",
        tuned_text=f"보정 {utterance_id}",
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

    def test_rejects_duplicate_id(self) -> None:
        manager = ConversationContextManager()
        manager.add(utterance(1))

        with self.assertRaises(ValueError):
            manager.add(utterance(1))

    def test_configurable_history_size(self) -> None:
        manager = ConversationContextManager(history_size=3)
        add_range(manager, 6)

        self.assert_context_ids(manager.get_context(), current=6, history=[3, 4, 5])

    def test_context_converts_to_json_serializable_dict(self) -> None:
        manager = ConversationContextManager()
        add_range(manager, 4)

        payload = manager.get_context().to_dict()

        self.assertEqual(4, payload["current"]["utterance_id"])
        self.assertEqual([1, 2, 3], [item["utterance_id"] for item in payload["history"]])
        json.dumps(payload)

    def assert_context_ids(
        self, context: ConversationContext, *, current: int, history: list[int]
    ) -> None:
        self.assertEqual(current, context.current.utterance_id)
        self.assertEqual(history, [item.utterance_id for item in context.history])
