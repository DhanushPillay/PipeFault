from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipefault.records import RunRecord
from pipefault.runstore import RunStore


def make_record(
    run_id: str = "run-abc", status: str = "completed", **overrides: object
) -> RunRecord:
    data: dict[str, object] = {
        "run_id": run_id,
        "dataset": "tlc",
        "task": "regression",
        "model": "lightgbm",
        "seed": 42,
        "config_hash": "a" * 64,
        "status": status,
    }
    data.update(overrides)
    return RunRecord(**data)  # type: ignore[arg-type]


def test_save_load_round_trip(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    record = make_record(metrics={"rmse": 7.2})

    path = store.save(record)

    assert path == tmp_path / "run-abc.json"
    assert store.load("run-abc") == record
    assert store.list_records() == [record]


def test_completed_run_is_skipped_unless_forced(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    store.save(make_record())

    assert not store.should_run("run-abc")
    with pytest.raises(FileExistsError):
        store.save(make_record(metrics={"rmse": 7.3}))

    store.save(make_record(metrics={"rmse": 7.3}), force=True)
    assert store.load("run-abc").metrics == {"rmse": 7.3}


def test_failed_run_can_retry(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    store.save(make_record(status="failed", reason="engine crashed"))

    assert store.should_run("run-abc")
    store.save(make_record(status="completed"))
    assert store.load("run-abc").status == "completed"


def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    store.save(make_record())

    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupt_record_raises(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    (tmp_path / "run-abc.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        store.load("run-abc")


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    store = RunStore(tmp_path)

    with pytest.raises(ValueError, match="invalid run id"):
        store.load("../evil")
    with pytest.raises(ValueError, match="invalid run id"):
        store.save(make_record(run_id="..\\evil"))
