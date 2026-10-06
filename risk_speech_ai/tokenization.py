"""Shared KoELECTRA sentence-pair preparation for training and inference.

The caller supplies a tokenizer, making the same function usable for a
TrainingSample and for live current/history text. No padding or truncation is
performed here; dynamic batch padding belongs to the future DataLoader.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .config import BASE_MODEL_NAME, MAX_HISTORY_UTTERANCES, MAX_SEQUENCE_LENGTH


class InputTooLongError(ValueError):
    """The current utterance alone exceeds the full sequence token budget."""

    def __init__(self, token_count: int, dropped_history_count: int) -> None:
        self.token_count = token_count
        self.dropped_history_count = dropped_history_count
        super().__init__(
            f"input_too_long: current-only pair has {token_count} tokens "
            f"(maximum {MAX_SEQUENCE_LENGTH})"
        )


class TokenizerContractError(ValueError):
    """Tokenizer does not supply the required KoELECTRA pair contract."""


@dataclass(frozen=True)
class TokenizedInput:
    input_ids: list[int]
    attention_mask: list[int]
    token_type_ids: list[int]
    used_history_texts: list[str]
    dropped_history_count: int
    token_count: int


def load_koelectra_tokenizer(revision: str | None = None) -> Any:
    """Load the designated Hugging Face tokenizer and verify its config.

    This downloads tokenizer/config assets on first use if they are not cached.
    It does not load model weights. Runtime pair output is checked by
    build_model_input before any encoding is returned to a caller.
    """

    try:
        from transformers import AutoConfig, AutoTokenizer
    except ImportError as error:
        raise RuntimeError("transformers is required for KoELECTRA tokenization") from error

    if revision is not None and (not isinstance(revision, str) or not revision.strip()):
        raise ValueError("revision must be a non-empty string or None")
    revision_kwargs = {"revision": revision} if revision is not None else {}
    config = AutoConfig.from_pretrained(BASE_MODEL_NAME, **revision_kwargs)
    if config.model_type != "electra" or config.type_vocab_size < 2:
        raise TokenizerContractError("KoELECTRA must support two token type IDs")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, **revision_kwargs)
    if "token_type_ids" not in tokenizer.model_input_names:
        raise TokenizerContractError("tokenizer does not expose token_type_ids")
    return tokenizer


def _encode_pair(tokenizer: Any, history_texts: Sequence[str], current_text: str) -> TokenizedInput:
    encoded = tokenizer(
        "\n".join(history_texts),
        text_pair=current_text,
        add_special_tokens=True,
        truncation=False,
        padding=False,
        return_attention_mask=True,
        return_token_type_ids=True,
    )
    try:
        input_ids = list(encoded["input_ids"])
        attention_mask = list(encoded["attention_mask"])
        token_type_ids = list(encoded["token_type_ids"])
        sep_token_id = tokenizer.sep_token_id
        cls_token_id = tokenizer.cls_token_id
    except (KeyError, TypeError, AttributeError) as error:
        raise TokenizerContractError("tokenizer omitted required pair fields") from error

    size = len(input_ids)
    if (
        size < 3
        or len(attention_mask) != size
        or len(token_type_ids) != size
        or input_ids[0] != cls_token_id
        or input_ids[-1] != sep_token_id
    ):
        raise TokenizerContractError("unexpected KoELECTRA pair structure")
    try:
        current_start = token_type_ids.index(1)
    except ValueError as error:
        raise TokenizerContractError("pair is missing the current segment") from error
    if (
        current_start < 2
        or current_start >= size
        or input_ids[current_start - 1] != sep_token_id
        or any(value != 0 for value in token_type_ids[:current_start])
        or any(value != 1 for value in token_type_ids[current_start:])
        or any(value != 1 for value in attention_mask)
    ):
        raise TokenizerContractError("token_type_ids do not distinguish history and current")
    return TokenizedInput(
        input_ids=input_ids,
        attention_mask=attention_mask,
        token_type_ids=token_type_ids,
        used_history_texts=list(history_texts),
        dropped_history_count=0,
        token_count=size,
    )


def build_model_input(
    history_texts: Sequence[str], current_text: str, *, tokenizer: Any
) -> TokenizedInput:
    """Encode one pair, dropping whole oldest history utterances as needed.

    Raises InputTooLongError if the empty-history/current pair still exceeds
    the budget. It never truncates any part of current or a history utterance.
    """

    if getattr(tokenizer, "padding_side", None) != "right":
        raise TokenizerContractError("tokenizer padding_side must be right for CLS pooling")
    if isinstance(history_texts, (str, bytes)) or not isinstance(history_texts, Sequence):
        raise ValueError("history_texts must be a sequence of strings")
    if any(not isinstance(text, str) or not text.strip() for text in history_texts):
        raise ValueError("history_texts must contain only non-empty strings")
    if not isinstance(current_text, str) or not current_text.strip():
        raise ValueError("current_text must be a non-empty string")

    used = list(history_texts[-MAX_HISTORY_UTTERANCES:])
    dropped = len(history_texts) - len(used)
    while True:
        result = _encode_pair(tokenizer, used, current_text)
        if result.token_count <= MAX_SEQUENCE_LENGTH:
            return TokenizedInput(
                input_ids=result.input_ids,
                attention_mask=result.attention_mask,
                token_type_ids=result.token_type_ids,
                used_history_texts=list(used),
                dropped_history_count=dropped,
                token_count=result.token_count,
            )
        if not used:
            raise InputTooLongError(result.token_count, dropped)
        used.pop(0)
        dropped += 1
