"""Evaluate whether the FP32 model's SECRET labels are usable for passwords.

This uses the checked-in tokenizer configuration without truncation and writes
the full per-case predictions to an ignored runtime report by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CACHED_PACKAGES = ROOT / ".runtime-build" / "python-packages"
if CACHED_PACKAGES.is_dir():
    sys.path.insert(0, str(CACHED_PACKAGES))

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


EXPECTED_MODEL_SHA256 = "7794bdaa2daaa524d1e7f5e4f80e6b62c6fe3bf36d7a9175f4cd4c011837ddc3"


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    expected_secret: str | None


CASES = (
    Case("plain_digits", "제 비밀번호는 1234입니다.", "1234"),
    Case("plain_word", "비밀번호는 password입니다.", "password"),
    Case("mixed", "비밀번호는 qwer1234입니다.", "qwer1234"),
    Case("mixed_case_symbol", "임시 비밀번호는 Abcd1234!입니다.", "Abcd1234!"),
    Case("stt_formal", "비밀번호는 4829 입니다.", "4829"),
    Case("stt_casual", "내 비번은 passWORD99예요.", "passWORD99"),
    Case("authentication_code", "인증번호는 839201입니다.", "839201"),
    Case("otp", "OTP 코드는 482913입니다.", "482913"),
    Case("pin", "PIN 번호는 2580입니다.", "2580"),
    Case("account_secret", "계정 암호는 hello123입니다.", "hello123"),
    Case("negative_general", "오늘 점심은 김치찌개입니다.", None),
    Case("negative_secret_word", "그 영화의 비밀은 마지막 장면입니다.", None),
    Case("negative_weather_number", "서울 날씨는 맑고 기온은 25도입니다.", None),
    Case("negative_policy", "회의에서 비밀번호 정책을 검토했습니다.", None),
    Case("negative_bus", "1234번 버스를 타고 회사에 갑니다.", None),
    Case("negative_instruction", "영문과 숫자를 섞어 입력하세요.", None),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / ".runtime-build" / "model" / "model.onnx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime-build" / "secret-evaluation.json",
    )
    return parser.parse_args()


def secret_spans(
    text: str,
    label_ids: list[int],
    offsets: list[tuple[int, int]],
    id2label: dict[int, str],
) -> list[dict[str, int | str]]:
    spans: list[list[int]] = []
    active: list[int] | None = None
    for label_id, (start, end) in zip(label_ids, offsets, strict=True):
        label = id2label[label_id]
        if label in {"B-SECRET", "I-SECRET"} and end > start:
            if label == "I-SECRET" and active is not None:
                active[1] = end
            else:
                if active is not None:
                    spans.append(active)
                active = [start, end]
        elif active is not None:
            spans.append(active)
            active = None
    if active is not None:
        spans.append(active)
    return [
        {"start": start, "endExclusive": end, "text": text[start:end]}
        for start, end in spans
    ]


def main() -> None:
    args = parse_args()
    model_bytes = args.model.read_bytes()
    model_sha256 = hashlib.sha256(model_bytes).hexdigest()
    if model_sha256 != EXPECTED_MODEL_SHA256:
        raise ValueError(f"Unexpected FP32 model SHA-256: {model_sha256}")

    config = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
    id2label = {int(key): value for key, value in config["id2label"].items()}
    tokenizer = AutoTokenizer.from_pretrained(
        Path(__file__).parent,
        local_files_only=True,
        use_fast=True,
    )
    tokenizer.backend_tokenizer.no_truncation()
    session = ort.InferenceSession(model_bytes, providers=["CPUExecutionProvider"])

    results = []
    positive_successes = 0
    negative_false_positives = 0
    for case in CASES:
        encoded = tokenizer(
            case.text,
            add_special_tokens=True,
            truncation=False,
            return_offsets_mapping=True,
            return_tensors="np",
        )
        inputs = {
            node.name: encoded[node.name].astype(np.int64)
            for node in session.get_inputs()
        }
        logits = session.run(["logits"], inputs)[0]
        if logits.shape != (1, len(encoded["input_ids"][0]), 59):
            raise ValueError(f"Unexpected logits shape for {case.name}: {logits.shape}")
        label_ids = logits.argmax(axis=-1)[0].tolist()
        spans = secret_spans(
            case.text,
            label_ids,
            [tuple(offset) for offset in encoded["offset_mapping"][0].tolist()],
            id2label,
        )
        expected_span = None
        if case.expected_secret is not None:
            start = case.text.index(case.expected_secret)
            expected_span = {
                "start": start,
                "endExclusive": start + len(case.expected_secret),
                "text": case.expected_secret,
            }
            positive_successes += int(spans == [expected_span])
        else:
            negative_false_positives += int(bool(spans))
        results.append(
            {
                **asdict(case),
                "expectedSpan": expected_span,
                "secretSpans": spans,
                "nonOutsideLabels": [
                    {
                        "token": token,
                        "label": id2label[label_id],
                        "start": offset[0],
                        "endExclusive": offset[1],
                    }
                    for token, label_id, offset in zip(
                        tokenizer.convert_ids_to_tokens(encoded["input_ids"][0]),
                        label_ids,
                        encoded["offset_mapping"][0].tolist(),
                        strict=True,
                    )
                    if id2label[label_id] != "O"
                ],
            }
        )

    positive_count = sum(case.expected_secret is not None for case in CASES)
    negative_count = len(CASES) - positive_count
    report = {
        "modelSha256": model_sha256,
        "onnxruntimeVersion": ort.__version__,
        "caseCount": len(CASES),
        "positiveCount": positive_count,
        "positiveExactSpanSuccesses": positive_successes,
        "negativeCount": negative_count,
        "negativeSecretFalsePositives": negative_false_positives,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
