# KoELECTRA NER tokenizer source

These files come from `atonlee/koelectra-ko-pii-ner` at immutable revision
`1e75c01e707232401883cf364151bbe2e560c708`.

| File | SHA-256 |
| --- | --- |
| `config.json` | `65b1c2e17c4eb6d4f5be29e4374784a03c7b886229af948757e55f3b79444a23` |
| `tokenizer.json` | `9bc85a2412ae3694bffac69cb152a9aafd59fd0357e540a343fa9daa62099c38` |
| `tokenizer_config.json` | `9cd988573a9588a6085cd353eeefa09b803dba75b03f58d0c1d302aad3078193` |

`tokenizer.json` contains a saved 256-token truncation policy even though
`tokenizer_config.json` and the model use a maximum length of 512. The Android
tokenizer deliberately applies no truncation. Window construction belongs to
the later detector implementation.

Run `generate_tokenizer_fixtures.py` with Transformers 5.10.2 to regenerate:

- `android/app/src/main/assets/models/koelectra-ko-pii-ner/vocab.txt`
- `android/app/src/test/resources/koelectra_tokenizer_golden.tsv`

The fixture stores the raw Python offsets and their converted Kotlin UTF-16
offsets. This makes supplementary Unicode handling explicit instead of treating
Python code-point indices as Kotlin string indices.
