from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest

from pipefault.data.provenance import add_provenance
from pipefault.features.tlc import PreparedTlc
from pipefault.runner import (
    SPLITS,
    ConditionResult,
    RunSpec,
    prepare_for_run,
    run_condition,
    run_pair,
)
from pipefault.runstore import RunStore


def _split(name: str, days: list[int]) -> pl.DataFrame:
    rows = [
        {
            "VendorID": vendor,
            "tpep_pickup_datetime": datetime(2024, 1, day, hour),
            "passenger_count": 1 + (zone % 3),
            "PULocationID": zone,
            "DOLocationID": 10 + zone,
            "zone_avg_duration_prior": float(20 + zone + day),
            "zone_trip_count_prior": float(100 + 10 * zone),
            "pickup_date": date(2024, 1, day),
            "pickup_hour": hour,
            "pickup_dow": (day - 1) % 7,
            "pickup_month": 1,
            "duration_min": float(10 + zone + hour / 10),
        }
        for day in days
        for zone in (1, 2, 3)
        for vendor in (1, 2)
        for hour in (8, 17)
    ]
    return add_provenance(pl.DataFrame(rows), dataset="tlc", file=f"{name}.parquet")


def _prepared() -> PreparedTlc:
    splits = {
        "train": _split("train", [1, 2, 3, 4]),
        "validation": _split("validation", [5]),
        "test": _split("test", [6]),
    }
    return PreparedTlc(
        splits=splits,
        raw_rows=sum(frame.height for frame in splits.values()),
        clean_rows=sum(frame.height for frame in splits.values()),
        files=("train.parquet", "validation.parquet", "test.parquet"),
    )


def _prediction_columns(result: ConditionResult) -> list[str]:
    return result.predictions["test"].columns


def test_clean_pair_is_identical_across_artifact_dirs(tmp_path: Path) -> None:
    prepared = prepare_for_run(_prepared(), seed=7)

    first, _ = run_pair(
        _prepared(), tmp_path / "a", defect="D5", severity=0.1, seed=7, num_boost_round=10
    )
    second, _ = run_pair(
        _prepared(), tmp_path / "b", defect="D5", severity=0.1, seed=7, num_boost_round=10
    )

    assert first.record.run_id == second.record.run_id
    assert first.record.metrics == second.record.metrics
    for split in SPLITS:
        assert first.predictions[split].equals(second.predictions[split])
    assert prepared.splits["train"].height < _prepared().splits["train"].height


def test_defect_pair_records_metadata_and_shares_rows(tmp_path: Path) -> None:
    clean, defect = run_pair(
        _prepared(), tmp_path, defect="D5", severity=0.25, seed=7, num_boost_round=10
    )

    assert defect.record.run_id != clean.record.run_id
    assert defect.record.metadata["defect"] == "D5"
    assert clean.record.metadata["defect"] is None
    assert clean.record.metadata["rows"] == defect.record.metadata["rows"]
    assert set(defect.record.metadata["injection"]) == set(SPLITS)

    clean_train = clean.predictions["train"].height
    assert defect.predictions["train"].height == clean_train + round(0.25 * clean_train)
    realized = defect.record.metadata["injection"]["train"]["realized_severity"]
    assert realized == pytest.approx(round(0.25 * clean_train) / clean_train)
    assert _prediction_columns(defect) == [
        "pf_row_id",
        "pf_occurrence",
        "batch_id",
        "y",
        "yhat",
    ]


def test_completed_run_is_skipped_without_force(tmp_path: Path) -> None:
    prepared = prepare_for_run(_prepared(), seed=7)
    spec = RunSpec(seed=7, num_boost_round=10, defect="D5", severity=0.1)

    first = run_condition(prepared, tmp_path, spec)
    prediction_path = tmp_path / "predictions" / spec.run_id / "test.parquet"
    prediction_path.unlink()
    second = run_condition(prepared, tmp_path, spec)

    assert second.record == first.record
    assert set(second.predictions) == {"train", "validation"}
    assert not prediction_path.exists()


def test_invalid_run_spec_is_rejected() -> None:
    with pytest.raises(ValueError, match="model"):
        RunSpec(model="linear")
    with pytest.raises(ValueError, match="severity"):
        RunSpec(severity=0.1)
    with pytest.raises(ValueError, match="severity"):
        RunSpec(defect="D5", severity=0.0)


@pytest.mark.parametrize("defect", ["D1", "D3", "D5", "D6"])
def test_all_pilot_defects_run_end_to_end(tmp_path: Path, defect: str) -> None:
    clean, injected = run_pair(
        _prepared(), tmp_path, defect=defect, severity=1 / 3, seed=7, num_boost_round=10
    )

    assert clean.record.status == "completed"
    assert injected.record.status == "completed"
    assert injected.record.metadata["defect"] == defect
    assert injected.record.metadata["injection"]["train"]["affected_rows"] > 0
    for split in SPLITS:
        assert (tmp_path / "predictions" / injected.record.run_id / f"{split}.parquet").exists()
    store = RunStore(tmp_path / "runs")
    loaded = store.load(injected.record.run_id)
    assert loaded.metadata["defect"] == defect
