"""Standalone NAME/ADDRESS smoke evaluation. No app integration or result files."""
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import time

MODEL_ID = "atonlee/koelectra-ko-pii-ner"
REVISION = "1e75c01e707232401883cf364151bbe2e560c708"
TARGETS = ("NAME", "ADDRESS")

MODEL_DIR = Path(__file__).resolve().parent / "onnx"
FILES = {
    "fp32": "model.onnx",
    "int8": "model_int8.onnx",
}



ANNOTATION = re.compile(r"\[(NAME|ADDRESS):([^\[\]]+)\]")


def parse_case(row):
    marked = row["annotated"]
    parts, gold = [], []
    cursor = 0
    length = 0
    for match in ANNOTATION.finditer(marked):
        prefix = marked[cursor:match.start()]
        parts.append(prefix)
        length += len(prefix)
        label, value = match.groups()
        gold.append((label, length, length + len(value)))
        parts.append(value)
        length += len(value)
        cursor = match.end()
    parts.append(marked[cursor:])
    text = "".join(parts)
    if not text.strip() or "[" in text or "]" in text:
        raise ValueError("Empty text or invalid annotation; use [NAME:value] / [ADDRESS:value].")
    return {"id": row["id"], "text": text, "gold": set(gold)}


def load_cases(path):
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(parse_case(json.loads(line)))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid case at line {number}: {exc}") from exc
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Cases must be nonempty and IDs must be unique.")
    return cases


def merge_bio(offsets, labels):
    """Merge adjacent same-type I tokens; recover orphan I as a new entity."""
    result = []
    active = None
    for (start, end), label in zip(offsets, labels):
        if start == end or label == "O":
            active = None
            continue
        prefix, entity = label.split("-", 1)
        if prefix == "I" and active is not None and result[active][0] == entity:
            kind, first, _ = result[active]
            result[active] = (kind, first, end)
        else:
            result.append((entity, start, end))
            active = len(result) - 1
    return result


def target_entities(entities):
    return {entity for entity in entities if entity[0] in TARGETS}


def mask(text, entities):
    for label, start, end in sorted(target_entities(entities), key=lambda e: e[1], reverse=True):
        tag = "PERSON" if label == "NAME" else "ADDRESS"
        text = text[:start] + f"[{tag}]" + text[end:]
    return text


def count_covered(gold, predicted):
    """Ignore predicted type, but only NAME/ADDRESS produce actual masks here."""
    covered_chars = {i for _, start, end in predicted for i in range(start, end)}
    return sum(all(i in covered_chars for i in range(start, end)) for _, start, end in gold)


def format_score(numerator, denominator):
    return f"{numerator / denominator:.1%}" if denominator else "N/A"


def show_metrics(counts):
    print("\nExact entity match (label + start + end):")
    print("label      gold  predicted  correct  precision  recall  F1")
    for label, (gold, predicted, correct) in counts.items():
        print(f"{label:10} {gold:4} {predicted:10} {correct:8}  "
              f"{format_score(correct, predicted):>9}  "
              f"{format_score(correct, gold):>6}  "
              f"{format_score(2 * correct, gold + predicted):>6}")


class Detector:
    def __init__(self, variant, download):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np

        def asset(name):
            path = MODEL_DIR / name
            if not path.is_file():
                raise FileNotFoundError(f"모델 파일이 없습니다 : {path}")

            return str(path)

        config = json.loads(Path(asset("config.json")).read_text(encoding="utf-8"))
        self.id2label = {int(k): v for k, v in config["id2label"].items()}
        self.tokenizer = Tokenizer.from_file(asset("tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.max_length = config["max_position_embeddings"]
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(asset(FILES[variant]), sess_options=options,
                                            providers=["CPUExecutionProvider"])

    def predict(self, text):
        started = time.perf_counter()
        encoding = self.tokenizer.encode(text, add_special_tokens=True)
        if len(encoding.ids) > self.max_length:
            raise ValueError(f"Input has {len(encoding.ids)} tokens; split into shorter utterances "
                             f"(maximum {self.max_length}). No silent truncation is allowed.")
        values = {"input_ids": encoding.ids, "attention_mask": encoding.attention_mask,
                  "token_type_ids": encoding.type_ids}
        types = {"tensor(int64)": self.np.int64, "tensor(int32)": self.np.int32}
        feed = {node.name: self.np.array([values[node.name]], dtype=types[node.type])
                for node in self.session.get_inputs()}
        logits = self.session.run(None, feed)[0]
        expected = (1, len(encoding.ids), len(self.id2label))
        if logits.shape != expected:
            raise ValueError(f"Unexpected logits shape {logits.shape}; expected {expected}")
        labels = [self.id2label[int(i)] for i in logits[0].argmax(axis=-1)]
        entities = merge_bio(encoding.offsets, labels)
        masked = mask(text, entities)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return entities, masked, elapsed_ms


def interactive(detector, cases_path):
    print("\n문장을 입력하고 Enter를 누르세요. 모델은 한 번만 불러옵니다.")
    print("/test: 예제 전체 평가 | /help: 도움말 | /quit: 종료")
    print("탐지는 모든 유형을 표시하며, 마스킹은 이름·주소만 적용합니다.")
    print("자유 입력에는 정답이 없으므로 정확도 점수를 계산하지 않습니다.")
    while True:
        try:
            text = input("\n문장 > ").strip()
            if not text:
                continue
            if text == "/quit":
                break
            if text == "/help":
                print("한 줄에 한 문장을 입력하세요. /test로 정답이 있는 예제를 평가합니다.")
                print("/quit 또는 Ctrl+C로 종료합니다. 입력과 결과는 파일에 저장하지 않습니다.")
                continue
            if text == "/test":
                evaluate(detector, load_cases(cases_path))
                continue
            entities, masked, elapsed = detector.predict(text)
            if not entities:
                print("탐지된 개체 없음")
            for label, start, end in entities:
                print(f"  {label:16} {text[start:end]!r} [{start}:{end}]")
            print(f"마스킹: {masked}\n처리 시간: {elapsed:.1f} ms")
        except (EOFError, KeyboardInterrupt):
            break
        except (ValueError, OSError) as exc:
            print(f"입력을 처리하지 못했습니다: {exc}")
    print("\n테스트를 종료했습니다.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=FILES, default="fp32")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.jsonl"))
    parser.add_argument("--text", help="Inspect a single unannotated sentence; no accuracy score.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Keep typing sentences using one loaded model.")
    parser.add_argument("--check-cases", action="store_true", help="Validate text cases without ML dependencies.")
    parser.add_argument("--download", action="store_true",
                        help="Explicitly allow downloading model files into the Hugging Face cache.")
    args = parser.parse_args()
    if args.interactive and (args.text is not None or args.check_cases):
        parser.error("--interactive cannot be combined with --text or --check-cases.")
    cases = ([] if args.interactive else
             [{"id": "custom", "text": args.text, "gold": None}] if args.text is not None
             else load_cases(args.cases))
    if any(not c["text"].strip() for c in cases):
        parser.error("Input must not be empty.")
    if args.check_cases:
        if args.text is not None:
            parser.error("--check-cases cannot be combined with --text.")
        print(f"Validated {len(cases)} cases, {sum(len(c['gold']) for c in cases)} entities.")
        return

    print(f"Model: {MODEL_ID}\nRevision: {REVISION}\nVariant: {args.variant}; CPU, 1 thread")
    try:
        detector = Detector(args.variant, args.download)
    except ImportError as exc:
        parser.exit(1, f"Missing dependency: {exc}. Install models/ner/requirements.txt.\n")
    except Exception as exc:
        parser.exit(1, f"Model initialization failed ({type(exc).__name__}): {exc}\n"
                    "Default mode uses cached files only. To permit downloads, use --download.\n")

    detector.predict("안녕하세요." if args.interactive else cases[0]["text"])  # Warm-up excluded.
    if args.interactive:
        interactive(detector, args.cases)
    else:
        evaluate(detector, cases)


def evaluate(detector, cases):
    counts = {label: [0, 0, 0] for label in (*TARGETS, "ALL")}
    timings = []
    covered = total_gold = missed_cases = positive_cases = negative_cases = false_positive_cases = 0
    for case in cases:
        entities, masked, ms = detector.predict(case["text"])
        timings.append(ms)
        predicted = target_entities(entities)
        print(f"\n[{case['id']}] {case['text']}")
        for label, start, end in entities:
            print(f"  {label:16} [{start}:{end}] {case['text'][start:end]!r}")
        print(f"  masked: {masked}\n  elapsed: {ms:.1f} ms")
        gold = case["gold"]
        if gold is None:
            continue
        for label in counts:
            g = {e for e in gold if label == "ALL" or e[0] == label}
            p = {e for e in predicted if label == "ALL" or e[0] == label}
            for index, value in enumerate((len(g), len(p), len(g & p))):
                counts[label][index] += value
        for title, items in (("MISSED/BOUNDARY", gold - predicted), ("EXTRA/BOUNDARY", predicted - gold)):
            for label, start, end in sorted(items):
                print(f"  {title}: {label} [{start}:{end}] {case['text'][start:end]!r}")
        full = count_covered(gold, predicted)
        total_gold += len(gold)
        covered += full
        positive_cases += bool(gold)
        missed_cases += full < len(gold)
        negative_cases += not gold
        false_positive_cases += not gold and bool(predicted)

    if all(case["gold"] is not None for case in cases):
        show_metrics(counts)
        print(f"Fully masked gold entities: {covered}/{total_gold} = {format_score(covered, total_gold)}")
        print(f"Positive cases with any unmasked gold characters: {missed_cases}/{positive_cases}")
        print(f"Negative cases with a NAME/ADDRESS false positive: {false_positive_cases}/{negative_cases}")
        print("These are scores on the supplied cases only, not a production/STT accuracy estimate.")
    print(f"Median latency: {statistics.median(timings):.1f} ms "
          "(tokenization + inference + decoding + masking; PC CPU, warm-up excluded).")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
