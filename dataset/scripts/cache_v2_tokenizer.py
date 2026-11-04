#!/usr/bin/env python3
"""Cache only the pinned public KoELECTRA tokenizer/config, never weights."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "artifacts/v2_runtime_assets/hf"
os.environ["HF_HOME"] = str(HOME)
os.environ["HF_HUB_CACHE"] = str(HOME / "hub")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import snapshot_download

REPO = "monologg/koelectra-base-v3-discriminator"
REVISION = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
snapshot = Path(snapshot_download(
    REPO, revision=REVISION, token=False, cache_dir=HOME / "hub",
    allow_patterns=["config.json", "vocab.txt", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"],
))
files = [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
         for path in sorted(snapshot.iterdir()) if path.is_file()]
assert any(path["path"].endswith("vocab.txt") for path in files)
assert not any(path["path"].endswith((".bin", ".safetensors", ".pt")) for path in files)
report = {"model": REPO, "revision": REVISION, "snapshot": str(snapshot.relative_to(ROOT)),
          "download_scope": "tokenizer_and_config_only_no_model_weights", "files": files}
target = ROOT / "reports/v2_pilot/ml_runtime/tokenizer_cache.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
