"""Environment-backed server configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_HISTORY_SIZE = 5


@dataclass(frozen=True)
class Settings:
    data_root: Path
    history_size: int = DEFAULT_HISTORY_SIZE

    def __post_init__(self) -> None:
        if not isinstance(self.data_root, Path):
            raise TypeError("data_root must be a Path")
        if (
            not isinstance(self.history_size, int)
            or isinstance(self.history_size, bool)
            or self.history_size < 0
        ):
            raise ValueError("history_size must be a non-negative integer")

    @property
    def corrections_root(self) -> Path:
        return self.data_root / "corrections"

    @property
    def contexts_root(self) -> Path:
        return self.data_root / "contexts"

    @classmethod
    def from_environment(cls) -> Settings:
        default_data_root = Path(__file__).resolve().parent / "data"
        configured_root = os.environ.get("PIC_DATA_ROOT")
        data_root = (
            Path(configured_root)
            if configured_root is not None and configured_root.strip()
            else default_data_root
        )

        history_value = os.environ.get(
            "PIC_CONTEXT_HISTORY_SIZE",
            str(DEFAULT_HISTORY_SIZE),
        )
        if not history_value.isdecimal():
            raise ValueError("PIC_CONTEXT_HISTORY_SIZE must be a non-negative integer")
        return cls(data_root=data_root, history_size=int(history_value))
