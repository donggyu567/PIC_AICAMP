"""Real KoELECTRA tokenizer checks; requires transformers and model access.

Run separately from the download-free unit tests. The tokenizer/config are
cached by Hugging Face after the first run; no model weights are loaded.
"""

import inspect
import json
import unittest

from transformers import AutoConfig

from risk_speech_ai.config import BASE_MODEL_NAME, MAX_SEQUENCE_LENGTH
from risk_speech_ai.checkpoint import tokenizer_metadata
from risk_speech_ai.tokenization import InputTooLongError, build_model_input, load_koelectra_tokenizer


class KoElectraIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_koelectra_tokenizer()
        cls.config = AutoConfig.from_pretrained(BASE_MODEL_NAME)

    @classmethod
    def _text_with_at_least(cls, token_count):
        text = "송금해주세요 "
        while len(cls.tokenizer(text, add_special_tokens=False)["input_ids"]) < token_count:
            text += "송금해주세요 "
        return text.strip()

    @classmethod
    def _pair_count(cls, history, current):
        return len(
            cls.tokenizer(
                "\n".join(history), text_pair=current,
                add_special_tokens=True, truncation=False,
            )["input_ids"]
        )

    def test_checkpoint_and_tokenizer_metadata(self):
        from transformers import ElectraModel

        tokenizer = self.tokenizer
        self.assertEqual("ElectraTokenizerFast", type(tokenizer).__name__)
        self.assertEqual(512, tokenizer.model_max_length)
        self.assertIn("token_type_ids", tokenizer.model_input_names)
        self.assertEqual("electra", self.config.model_type)
        self.assertEqual(2, self.config.type_vocab_size)
        self.assertIn("token_type_ids", inspect.signature(ElectraModel.forward).parameters)
        self.assertEqual(("[CLS]", 2), (tokenizer.cls_token, tokenizer.cls_token_id))
        self.assertEqual(("[SEP]", 3), (tokenizer.sep_token, tokenizer.sep_token_id))
        self.assertEqual(("[PAD]", 0), (tokenizer.pad_token, tokenizer.pad_token_id))

    def test_real_tokenizer_checkpoint_identity_is_serializable(self):
        identity = tokenizer_metadata(self.tokenizer)
        self.assertEqual(BASE_MODEL_NAME, identity["name"])
        self.assertEqual(self.tokenizer.vocab_size, identity["vocab_size"])
        self.assertEqual("right", identity["padding_side"])
        self.assertEqual(64, len(identity["vocab_sha256"]))
        json.dumps(identity, allow_nan=False)

    def test_real_sentence_pair_segments_and_special_tokens(self):
        result = build_model_input(
            ["안녕하세요.", "금융감독원입니다."],
            "지금 안전계좌로 송금해주세요.", tokenizer=self.tokenizer,
        )
        tokens = self.tokenizer.convert_ids_to_tokens(result.input_ids)
        boundary = result.token_type_ids.index(1)
        self.assertEqual("[CLS]", tokens[0])
        self.assertEqual("[SEP]", tokens[boundary - 1])
        self.assertEqual("[SEP]", tokens[-1])
        self.assertEqual([0] * boundary, result.token_type_ids[:boundary])
        self.assertEqual([1] * (result.token_count - boundary), result.token_type_ids[boundary:])
        self.assertEqual([1] * result.token_count, result.attention_mask)
        self.assertEqual(len(result.input_ids), len(result.token_type_ids))
        self.assertEqual(0, result.dropped_history_count)
        self.assertEqual(2, len(result.used_history_texts))

    def test_empty_history_still_has_two_sequences(self):
        result = build_model_input([], "지금 계좌번호를 말씀해주세요.", tokenizer=self.tokenizer)
        self.assertEqual(
            [self.tokenizer.cls_token_id, self.tokenizer.sep_token_id],
            result.input_ids[:2],
        )
        self.assertEqual([0, 0], result.token_type_ids[:2])
        self.assertTrue(all(value == 1 for value in result.token_type_ids[2:]))
        self.assertEqual(self.tokenizer.sep_token_id, result.input_ids[-1])

    def test_exact_512_boundary_and_current_token_identity(self):
        current = " ".join(["가"] * 509)
        current_ids = self.tokenizer(current, add_special_tokens=False)["input_ids"]
        self.assertEqual(509, len(current_ids))
        result = build_model_input(["오래된 발화"], current, tokenizer=self.tokenizer)
        self.assertEqual(512, result.token_count)
        self.assertEqual([], result.used_history_texts)
        self.assertEqual(1, result.dropped_history_count)
        self.assertEqual(current_ids, result.input_ids[2:-1])
        with self.assertRaises(InputTooLongError) as caught:
            build_model_input([], current + " 가", tokenizer=self.tokenizer)
        self.assertEqual(513, caught.exception.token_count)

    def test_case_a_short_input_keeps_all_history(self):
        history = ["안녕하세요.", "금융감독원입니다."]
        result = build_model_input(history, "지금 안전계좌로 송금해주세요.", tokenizer=self.tokenizer)
        self.assertLess(result.token_count, MAX_SEQUENCE_LENGTH)
        self.assertEqual(0, result.dropped_history_count)
        self.assertEqual(history, result.used_history_texts)

    def test_case_b_drops_one_oldest_history(self):
        history = [self._text_with_at_least(260), self._text_with_at_least(260)]
        current = self._text_with_at_least(20)
        self.assertGreater(self._pair_count(history, current), MAX_SEQUENCE_LENGTH)
        self.assertLessEqual(self._pair_count(history[1:], current), MAX_SEQUENCE_LENGTH)
        result = build_model_input(history, current, tokenizer=self.tokenizer)
        self.assertEqual(1, result.dropped_history_count)
        self.assertEqual(history[1:], result.used_history_texts)
        self.assertLessEqual(result.token_count, MAX_SEQUENCE_LENGTH)

    def test_case_c_drops_multiple_histories_oldest_first(self):
        history = [self._text_with_at_least(170) + str(i) for i in range(5)]
        current = self._text_with_at_least(20)
        self.assertGreater(self._pair_count(history, current), MAX_SEQUENCE_LENGTH)
        result = build_model_input(history, current, tokenizer=self.tokenizer)
        self.assertGreater(result.dropped_history_count, 1)
        self.assertEqual(history[result.dropped_history_count:], result.used_history_texts)
        self.assertLessEqual(result.token_count, MAX_SEQUENCE_LENGTH)

    def test_case_d_drops_all_histories_but_keeps_current(self):
        history = [self._text_with_at_least(100) + str(i) for i in range(5)]
        current = self._text_with_at_least(480)
        self.assertLessEqual(self._pair_count([], current), MAX_SEQUENCE_LENGTH)
        self.assertGreater(self._pair_count(history[-1:], current), MAX_SEQUENCE_LENGTH)
        result = build_model_input(history, current, tokenizer=self.tokenizer)
        self.assertEqual(5, result.dropped_history_count)
        self.assertEqual([], result.used_history_texts)
        self.assertEqual(self._pair_count([], current), result.token_count)

    def test_case_e_current_only_overflow_is_an_error(self):
        current = self._text_with_at_least(515)
        self.assertGreater(self._pair_count([], current), MAX_SEQUENCE_LENGTH)
        with self.assertRaises(InputTooLongError) as caught:
            build_model_input(["안녕하세요."], current, tokenizer=self.tokenizer)
        self.assertGreater(caught.exception.token_count, MAX_SEQUENCE_LENGTH)
        self.assertEqual(1, caught.exception.dropped_history_count)


if __name__ == "__main__":
    unittest.main()
