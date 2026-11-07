"""Atomic run storage with completed-run resume semantics."""

from __future__ import annotations

import os
import re
from pathlib import Path

from pipefault.records import RunRecord

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
TERMINAL_STATUSES = frozenset({"completed", "skipped"})


class RunStore:
    """Store one JSON record per run id under a single directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(f"invalid run id: {run_id!r}")
        return self.root / f"{run_id}.json"

    def save(self, record: RunRecord, *, force: bool = False) -> Path:
        path = self._path(record.run_id)
        if path.exists() and not force:
            existing = self.load(record.run_id)
            if existing.status in TERMINAL_STATUSES:
                raise FileExistsError(f"run {record.run_id!r} already {existing.status}")

        self.root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(record.to_json())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return path

    def load(self, run_id: str) -> RunRecord:
        return RunRecord.from_json(self._path(run_id).read_text(encoding="utf-8"))

    def is_complete(self, run_id: str) -> bool:
        try:
            return self.load(run_id).status == "completed"
        except FileNotFoundError:
            return False

    def should_run(self, run_id: str, *, force: bool = False) -> bool:
        return force or not self.is_complete(run_id)

    def list_records(self) -> list[RunRecord]:
        if not self.root.exists():
            return []
        return [
            RunRecord.from_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]
