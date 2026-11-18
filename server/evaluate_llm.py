"""Evaluate PIC's real-time LLM prompt using synthetic masked conversations."""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAIError

from models.llm_correction import MaskedTranscript
from server.analysis.context_contracts import (
    ContextRiskInput,
    PreparedUtterance,
    parse_prepared_utterance,
)
from server.analysis.context_service import SYSTEM_PROMPT, create_llm_client

ROOT = Path(__file__).resolve().parents[1]


def read_cases(path):
    cases = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Input must be a nonempty JSON array.")
    prepared = []
    seen = set()
    for case in cases:
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("Each case_id must be a unique nonempty string.")
        seen.add(case_id)
        context = ContextRiskInput.model_validate(case["context"])
        ids = [item.utterance_id for item in context.utterances]
        if ids != list(range(1, len(ids) + 1)) or context.current_utterance_id != ids[-1]:
            raise ValueError(f"{case_id}: IDs must be 1..N, and the final item must be current.")
        current = context.utterances[-1]
        # Reuse the server's masking-contract validation for the current input.
        tokens = []
        for token in re.findall(r"\[([^\[\]\r\n]+)\]", current.text):
            if token not in tokens:
                tokens.append(token)
        MaskedTranscript(
            schema_version="1.0", conversation_id=context.conversation_id,
            utterance_id=current.utterance_id, masked_text=current.text,
            has_masked_data=bool(tokens), masked_types=tuple(tokens),
        )
        expected = case.get("expected_assessment")
        if expected is not None and expected not in {
            "suspicious", "no_clear_risk", "insufficient_context"
        }:
            raise ValueError(f"{case_id}: invalid expected_assessment.")
        prepared.append((case_id, context, expected))
    return prepared


def evaluate(client, case, model, effort, tier, repetition):
    case_id, context, expected = case
    record = {
        "case_id": case_id,
        "repeat": repetition,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_model": model,
        "requested_service_tier": tier,
        "reasoning_effort": effort,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "expected_assessment": expected,
        "input": context.model_dump(),
        "usage": None,
        "raw_output": None,
        "result": None,
        "error_type": None,
    }
    started = perf_counter()
    try:
        response = client.responses.create(
            model=model, reasoning={"effort": effort}, service_tier=tier,
            instructions=SYSTEM_PROMPT,
            input=context.model_dump_json(exclude={"conversation_id"}),
            store=False, truncation="disabled", max_output_tokens=2048,
            text={"format": {
                "type": "json_schema", "name": "prepared_utterance",
                "strict": True, "schema": PreparedUtterance.model_json_schema(),
            }},
        )
        record.update(
            api_seconds=round(perf_counter() - started, 4),
            returned_model=response.model,
            returned_service_tier=response.service_tier,
            response_status=response.status,
            request_id=getattr(response, "_request_id", None),
            usage=response.usage.model_dump() if response.usage else None,
            raw_output=response.output_text,
        )
        refused = any(
            part.type == "refusal"
            for item in response.output if item.type == "message"
            for part in item.content
        )
        if response.status != "completed" or refused:
            raise ValueError("Response incomplete or refused.")
        result = parse_prepared_utterance(response.output_text, context)
        record["result"] = result.model_dump()
        record["status"] = "ok"
        record["assessment_match"] = (
            result.context_judgment.assessment == expected if expected is not None else None
        )
    except (OpenAIError, ValueError) as error:
        record["status"] = "error"
        record["error_type"] = type(error).__name__
        record["assessment_match"] = None
        record.setdefault("api_seconds", round(perf_counter() - started, 4))
    record["total_seconds"] = round(perf_counter() - started, 4)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--effort", default="low")
    parser.add_argument("--service-tier", choices=("fast", "default", "flex"), default="fast")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive.")
    cases = read_cases(args.input)
    if args.validate_only:
        print(f"Validated {len(cases)} cases; no API calls.")
        return 0
    if args.output is None:
        parser.error("--output is required for API evaluation.")
    load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")
    model = args.model or os.getenv("PIC_CONTEXT_MODEL", "").strip()
    client = create_llm_client()
    if not model or client is None:
        parser.error("Configure OPENAI_API_KEY and PIC_CONTEXT_MODEL in the project environment.")
    failed = 0
    try:
        # Refuse to overwrite a previous run. Flush each completed case for recovery.
        with args.output.open("x", encoding="utf-8") as destination:
            for repetition in range(1, args.repeat + 1):
                for case in cases:
                    record = evaluate(
                        client, case, model, args.effort, args.service_tier, repetition
                    )
                    destination.write(json.dumps(record, ensure_ascii=False) + "\n")
                    destination.flush()
                    failed += record["status"] != "ok"
                    print(f'{record["case_id"]} #{repetition}: {record["status"]}', flush=True)
    finally:
        client.close()
    print(f"Finished {len(cases) * args.repeat} calls; failures={failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
