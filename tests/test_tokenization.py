"""Sentence-pair and full-sequence budget tests without model downloads."""

import unittest
from unittest.mock import patch

from risk_speech_ai.tokenization import (
    InputTooLongError,
    TokenizerContractError,
    build_model_input,
)
from risk_speech_ai.training_data import TrainingSample, build_training_samples


class PairTokenizer:
    """Small stand-in with the BERT/ELECTRA pair and segment contract."""

    cls_token_id = 101
    sep_token_id = 102
    model_input_names = ["input_ids", "attention_mask", "token_type_ids"]
    padding_side = "right"

    def __init__(self):
        self.calls = []
        self.vocab = {}

    def _ids(self, text):
        ids = []
        for word in text.split():
            ids.append(self.vocab.setdefault(word, len(self.vocab) + 1000))
        return ids

    def __call__(self, text, *, text_pair, **options):
        self.calls.append((text, text_pair, options))
        first, second = self._ids(text), self._ids(text_pair)
        input_ids = [101, *first, 102, *second, 102]
        return {
            "input_ids": input_ids,
            "attention_mask": [1] * len(input_ids),
            "token_type_ids": [0] * (len(first) + 2) + [1] * (len(second) + 1),
        }


def words(count):
    return " ".join(f"word{i}" for i in range(count))


class PairTests(unittest.TestCase):
    def test_koelectra_loader_passes_requested_revision_to_both_assets(self):
        from risk_speech_ai.config import BASE_MODEL_NAME
        from risk_speech_ai.tokenization import load_koelectra_tokenizer

        config = type("Config", (), {"model_type": "electra", "type_vocab_size": 2})()
        tokenizer = type("Tokenizer", (), {"model_input_names": ["token_type_ids"]})()
        with patch("transformers.AutoConfig.from_pretrained", return_value=config) as load_config, \
             patch("transformers.AutoTokenizer.from_pretrained", return_value=tokenizer) as load_tokenizer:
            self.assertIs(tokenizer, load_koelectra_tokenizer(revision="commit-123"))
        load_config.assert_called_once_with(BASE_MODEL_NAME, revision="commit-123")
        load_tokenizer.assert_called_once_with(BASE_MODEL_NAME, revision="commit-123")

    def test_history_is_first_and_current_second_with_newlines(self):
        tokenizer = PairTokenizer()
        result = build_model_input(["안녕하세요.", "금융감독원입니다."], "계좌번호를 말씀해주세요.", tokenizer=tokenizer)
        first, second, options = tokenizer.calls[0]
        self.assertEqual("안녕하세요.\n금융감독원입니다.", first)
        self.assertEqual("계좌번호를 말씀해주세요.", second)
        self.assertEqual([101, 1000, 1001, 102, 1002, 1003, 102], result.input_ids)
        self.assertEqual([0, 0, 0, 0, 1, 1, 1], result.token_type_ids)
        self.assertEqual(7, result.token_count)
        self.assertEqual([1] * result.token_count, result.attention_mask)
        self.assertFalse(options["truncation"])
        self.assertFalse(options["padding"])

    def test_empty_history_uses_same_pair_path(self):
        tokenizer = PairTokenizer()
        result = build_model_input([], "current", tokenizer=tokenizer)
        self.assertEqual(("", "current"), tokenizer.calls[0][:2])
        self.assertEqual([101, 102, 1000, 102], result.input_ids)
        self.assertEqual([0, 0, 1, 1], result.token_type_ids)

    def test_missing_segment_ids_is_explicit_error(self):
        class NoSegments(PairTokenizer):
            def __call__(self, text, *, text_pair, **options):
                result = super().__call__(text, text_pair=text_pair, **options)
                del result["token_type_ids"]
                return result

        with self.assertRaises(TokenizerContractError):
            build_model_input([], "current", tokenizer=NoSegments())

    def test_training_and_live_text_use_the_same_function(self):
        sample = TrainingSample("P0001", 2, ["history"], "current", 1.0, [0] * 8)
        tokenizer = PairTokenizer()
        trained = build_model_input(sample.history_texts, sample.current_text, tokenizer=tokenizer)
        live = build_model_input(["history"], "current", tokenizer=tokenizer)
        self.assertEqual(trained, live)


class SequenceBudgetTests(unittest.TestCase):
    def test_short_pair_keeps_history(self):
        result = build_model_input(["old", "new"], "current", tokenizer=PairTokenizer())
        self.assertEqual(["old", "new"], result.used_history_texts)
        self.assertEqual(0, result.dropped_history_count)
        self.assertEqual(6, result.token_count)

    def test_one_oldest_history_removed(self):
        result = build_model_input(["old", "new"], words(508), tokenizer=PairTokenizer())
        self.assertEqual(["new"], result.used_history_texts)
        self.assertEqual(1, result.dropped_history_count)
        self.assertEqual(512, result.token_count)

    def test_multiple_oldest_histories_removed(self):
        history = [f"h{i}" for i in range(5)]
        result = build_model_input(history, words(507), tokenizer=PairTokenizer())
        self.assertEqual(["h3", "h4"], result.used_history_texts)
        self.assertEqual(3, result.dropped_history_count)
        self.assertEqual(512, result.token_count)

    def test_all_five_histories_removed_and_current_preserved(self):
        tokenizer = PairTokenizer()
        result = build_model_input([f"h{i}" for i in range(5)], words(509), tokenizer=tokenizer)
        self.assertEqual([], result.used_history_texts)
        self.assertEqual(5, result.dropped_history_count)
        self.assertEqual(512, result.token_count)
        self.assertEqual(words(509), tokenizer.calls[-1][1])

    def test_current_only_at_limit(self):
        result = build_model_input([], words(509), tokenizer=PairTokenizer())
        self.assertEqual(512, result.token_count)

    def test_current_only_over_limit_raises_without_truncation(self):
        tokenizer = PairTokenizer()
        with self.assertRaises(InputTooLongError) as caught:
            build_model_input(["old"], words(510), tokenizer=tokenizer)
        self.assertEqual(513, caught.exception.token_count)
        self.assertEqual(1, caught.exception.dropped_history_count)
        self.assertTrue(all(call[2]["truncation"] is False for call in tokenizer.calls))

    def test_more_than_five_histories_keeps_newest_five(self):
        result = build_model_input([f"h{i}" for i in range(7)], "current", tokenizer=PairTokenizer())
        self.assertEqual([f"h{i}" for i in range(2, 7)], result.used_history_texts)
        self.assertEqual(2, result.dropped_history_count)


class LeakageTests(unittest.TestCase):
    def test_join_to_tokenizer_excludes_metadata_future_and_other_calls(self):
        rows = [
            {"conversation_id": conversation, "utterance_id": index,
             "tuned_text": text, "raw_text": "RAW_SENTINEL",
             "masked_text": "MASKED_SENTINEL", "is_tuned": "TUNED_SENTINEL",
             "has_unclear": "UNCLEAR_SENTINEL"}
            for conversation, index, text in (
                ("P0001", 1, "tuned history"), ("P0001", 2, "tuned current"),
                ("P0001", 3, "FUTURE_SENTINEL"), ("P0002", 1, "OTHER_CALL_SENTINEL"),
            )
        ]
        labels = [{"conversation_id": "P0001", "utterance_id": 2,
                   "label_status": "reviewed", "is_phishing": True,
                   "labels": ["money_transfer"]}]
        sample = build_training_samples(labels, rows).samples[0]
        tokenizer = PairTokenizer()
        build_model_input(sample.history_texts, sample.current_text, tokenizer=tokenizer)
        self.assertEqual(("tuned history", "tuned current"), tokenizer.calls[0][:2])

    def test_only_tuned_history_and_current_reach_tokenizer(self):
        tokenizer = PairTokenizer()
        sample = TrainingSample("P0001", 2, ["tuned history"], "tuned current", 1.0, [1] + [0] * 7)
        build_model_input(sample.history_texts, sample.current_text, tokenizer=tokenizer)
        first, second, _ = tokenizer.calls[0]
        self.assertEqual(("tuned history", "tuned current"), (first, second))
        for forbidden in ("is_phishing", "labels", "label_status", "raw_text", "masked_text"):
            self.assertNotIn(forbidden, first + second)


if __name__ == "__main__":
    unittest.main()
