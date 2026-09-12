"""Generate the Android vocab and Python tokenizer golden fixture.

Run with Transformers 5.10.2, the version recorded by config.json. The source
tokenizer contains a stale 256-token truncation setting; every encode below
explicitly disables it so windowing can be handled by the detector later.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer
import tokenizers
import transformers


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = "1e75c01e707232401883cf364151bbe2e560c708"
EXPECTED = {
    "config.json": "65b1c2e17c4eb6d4f5be29e4374784a03c7b886229af948757e55f3b79444a23",
    "tokenizer.json": "9bc85a2412ae3694bffac69cb152a9aafd59fd0357e540a343fa9daa62099c38",
    "tokenizer_config.json": "9cd988573a9588a6085cd353eeefa09b803dba75b03f58d0c1d302aad3078193",
}
VOCAB_OUTPUT = ROOT / "android/app/src/main/assets/models/koelectra-ko-pii-ner/vocab.txt"
GOLDEN_OUTPUT = ROOT / "android/app/src/test/resources/koelectra_tokenizer_golden.tsv"

CASES = {
    "korean_pii": "김민준 씨한테 010-1234-5678로 연락해줘",
    "english_and_numbers": "Hello ABC xyz 12345",
    "whitespace_and_punctuation": "  서울\t강남구\n테헤란로 152! ",
    "unicode_whitespace_and_punctuation": "가\u00a0나\u2003다—라…마",
    "surrogate_pairs": "이모지😀김철수🚀 끝",
    "unknown_and_special_literals": "𠀀 [UNK] A[UNK]B",
    "combining_and_non_ascii": "Cafe\u0301 naïve",
    "unassigned_code_point": "ab\u0378cd",
    "mixed_punctuation": "한글-English_123@example.com",
    "over_model_limit_without_truncation": "가 " * 600,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def utf16_index(text: str, python_index: int) -> int:
    return len(text[:python_index].encode("utf-16-le")) // 2


def main() -> None:
    for name, expected in EXPECTED.items():
        actual = sha256(HERE / name)
        if actual != expected:
            raise ValueError(f"Unexpected {name}: {actual}")
    if transformers.__version__ != "5.10.2":
        raise ValueError(f"Expected Transformers 5.10.2, got {transformers.__version__}")

    raw = json.loads((HERE / "tokenizer.json").read_text(encoding="utf-8"))
    vocab = raw["model"]["vocab"]
    ordered = sorted(vocab, key=vocab.get)
    if [vocab[token] for token in ordered] != list(range(35_000)):
        raise ValueError("Vocabulary ids are not contiguous 0..34999")
    VOCAB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    VOCAB_OUTPUT.write_text("\n".join(ordered) + "\n", encoding="utf-8", newline="\n")

    tokenizer = AutoTokenizer.from_pretrained(HERE, local_files_only=True, use_fast=True)
    lines = [
        "# koelectra-ko-pii-ner Python tokenizer golden v1",
        f"# revision={REVISION}",
        f"# tokenizer_sha256={EXPECTED['tokenizer.json']}",
        f"# transformers={transformers.__version__}",
        f"# tokenizers={tokenizers.__version__}",
        "# truncation=false",
        "# TOKEN fields: id, base64(UTF-8 token), Python start/end, Kotlin UTF-16 start/end",
    ]
    for name, text in CASES.items():
        encoded = tokenizer(
            text,
            add_special_tokens=True,
            return_attention_mask=True,
            return_offsets_mapping=True,
            truncation=False,
            padding=False,
        )
        tokens = tokenizer.convert_ids_to_tokens(encoded["input_ids"])
        if len(tokens) != len(encoded["offset_mapping"]):
            raise ValueError(f"Mismatched Python output lengths for {name}")
        lines.append(f"CASE\t{name}\t{b64(text)}")
        for token_id, token, (start, end) in zip(
            encoded["input_ids"], tokens, encoded["offset_mapping"], strict=True
        ):
            lines.append(
                "\t".join(
                    map(
                        str,
                        (
                            "TOKEN",
                            token_id,
                            b64(token),
                            start,
                            end,
                            utf16_index(text, start),
                            utf16_index(text, end),
                        ),
                    )
                )
            )
        if any(value != 1 for value in encoded["attention_mask"]):
            raise ValueError(f"Unexpected attention mask for {name}")
        lines.append("END")
    GOLDEN_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(ordered)} tokens to {VOCAB_OUTPUT}")
    print(f"Wrote {len(CASES)} cases to {GOLDEN_OUTPUT}")


if __name__ == "__main__":
    main()
