"""Durable, append-only logs for future training runs."""

from __future__ import annotations

import ctypes
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def working_set_bytes() -> int | None:
    """Current process resident bytes when the OS exposes them."""
    if os.name != "nt":
        try:
            import resource
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        except (ImportError, OSError):
            return None
    try:
        class MemoryCounters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("page_fault_count", ctypes.c_uint32),
                        ("peak_working_set_size", ctypes.c_size_t),
                        ("working_set_size", ctypes.c_size_t),
                        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                        ("quota_paged_pool_usage", ctypes.c_size_t),
                        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                        ("quota_non_paged_pool_usage", ctypes.c_size_t),
                        ("pagefile_usage", ctypes.c_size_t),
                        ("peak_pagefile_usage", ctypes.c_size_t)]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)
        get_memory.restype = ctypes.c_int
        if get_memory(get_process(), ctypes.byref(counters), counters.cb):
            return int(counters.working_set_size)
    except (AttributeError, OSError, ValueError):
        pass
    return None


class TrainingJournal:
    def __init__(self, base_dir: Path, metadata: dict) -> None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
        self.path = base_dir / run_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.batch = (self.path / "batches.jsonl").open("x", encoding="utf-8", newline="\n")
        self.epoch = (self.path / "epochs.jsonl").open("x", encoding="utf-8", newline="\n")
        with (self.path / "run.json").open("x", encoding="utf-8") as stream:
            json.dump({"run_id": run_id, "started_utc": datetime.now(timezone.utc).isoformat(),
                       **metadata}, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _append(stream, row: dict) -> None:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

    def log_batch(self, row: dict) -> None:
        self._append(self.batch, row)

    def log_epoch(self, row: dict) -> None:
        self._append(self.epoch, row)

    def close(self) -> None:
        self.batch.close()
        self.epoch.close()

    def __enter__(self) -> "TrainingJournal":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
