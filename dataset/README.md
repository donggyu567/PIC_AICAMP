# Voice-phishing AI dataset workspace

## Purpose

This is the collection and normalization workspace for a voice-phishing detection dataset. The long-term target is at least 500 phishing-related utterances and 300 normal-conversation utterances. It currently contains only the directory structure, source registry schema, examples, and validation workflow; it contains no real collection data.

## A-owner scope

The A owner records source information, separates calls into utterances, assigns IDs, identifies speakers with neutral IDs, preserves original utterance text, and records sources. Classification fields are out of scope.

## Layout

```text
dataset/
|- raw/                    # real collected candidate data only
|  |- phishing/
|  `- normal/
|- examples/               # schema-only sample JSON
|- staging/                # B-owner intermediate work
|- processed/              # final JSONL output
|- metadata/source_registry.csv
|- scripts/validate_raw.py
`- README.md
```

## `raw/`: real collection data only

`dataset/raw/` stores only genuinely collected candidate training data. It is intentionally empty now, except for `.gitkeep` files used to retain its directories in Git.

When collection begins, use one JSON file per utterance:

```text
raw/phishing/P0001/utterance_001.json
raw/normal/N0001/utterance_001.json
```

Real phishing IDs start at `P0001`, `P0002`, and so on; real normal IDs start at `N0001`, `N0002`, and so on.

## `examples/`: schema-only data

`dataset/examples/` has one phishing and one normal JSON example for documentation and development tests.

- It is not real collected data or a transcript.
- It is not used for training or evaluation.
- It is not included in dataset statistics.
- `validate_raw.py` does not inspect it.

The `P0001` and `N0001` IDs in the examples are schema illustrations only. They do not reserve or assign real collection IDs; real data starts at these IDs independently under `raw/`.

## Raw JSON schema

```json
{
  "conversation_id": "P0001",
  "utterance_id": 1,
  "speaker": "speaker_A",
  "text": "Original utterance text",
  "source": "Source name"
}
```

- `conversation_id` matches `^[PN]\\d{4}$`, uses `P` under `raw/phishing/` and `N` under `raw/normal/`, and matches its parent directory.
- `utterance_id` is a positive integer, normally consecutive from 1 per conversation, and matches `utterance_NNN.json`.
- `speaker` is exactly `speaker_A`, `speaker_B`, or `unknown`.
- `text` cannot be empty or whitespace-only.
- `source` is a non-empty source name; never invent unavailable provenance or URLs.

## Speaker rules

Allowed values are `speaker_A`, `speaker_B`, and `unknown`.

Within one `conversation_id`, use the same speaker ID consistently for the same person. `speaker_A` and `speaker_B` are neutral identifiers only: neither implies a scammer, victim, caller, callee, agent, customer, or any other real-world role. The A/B assignment may therefore represent different real-world roles in different conversations.

Use the same neutral convention for both phishing and normal data. Neutral IDs prevent role information from becoming a label-leakage hint that lets a model predict phishing versus normal data without relying on utterance content. If the source cannot reliably distinguish a speaker, use `unknown` rather than guessing an A/B ID.

The current prototype is designed for two-person conversations. Do not merge three or more real speakers into two IDs or extend this schema ad hoc; flag those conversations for separate review.

## Source registry

Record verified real sources in `metadata/source_registry.csv`. Unknown URLs, counts, transcript availability, and license information must be left blank or noted as unknown, never guessed. The registry has only its header until real sources are collected. Verify license and redistribution conditions before adding real transcripts to GitHub.

## Validation

Run from the repository root:

```bash
python dataset/scripts/validate_raw.py
```

The standard-library-only validator scans only `dataset/raw/phishing/` and `dataset/raw/normal/`; it excludes `examples/`, `staging/`, `processed/`, and `metadata/`. Empty raw directories are valid and report zero conversations and utterances.

It checks JSON syntax, required fields, field values, directory/ID agreement, filename/utterance-ID agreement, duplicate records and utterance IDs, and non-consecutive utterance numbers.

## B-owner handoff

The B owner may later add `is_phishing` and `labels` during labeling or processing, not to raw records. Raw data preserves source material and provenance; processed data is the derived, label-ready JSONL output.
