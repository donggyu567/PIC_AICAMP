"""Run the deterministic Shim-Pick v0.1 mock analysis."""

import json
from pathlib import Path

from ai.analyzer import analyze_grids


def main() -> None:
    with (Path(__file__).parent / "mocks" / "grids.json").open(encoding="utf-8") as file:
        print(json.dumps(analyze_grids(json.load(file)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
