from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN, add_provenance
from pipefault.inject.duplicate import DuplicateIngestion
from pipefault.simulate.replay import INGEST_TIME, ReplaySpec, replay


def _replayed(rows: int = 100) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    frame = add_provenance(
        pl.DataFrame({"tpep_pickup_datetime": [start + timedelta(minutes=i) for i in range(rows)]}),
        dataset="tlc",
        file="a.parquet",
    )
    return replay(frame, ReplaySpec(time_column="tpep_pickup_datetime", seed=42))


def test_duplicate_count_is_exact_and_rows_are_copies() -> None:
    frame = _replayed()

    result = DuplicateIngestion().apply(frame, severity=0.10, seed=7)

    assert result.data.height == 110
    assert result.affected_rows == 10
    assert result.affected_units == 10
    assert result.realized_severity == pytest.approx(0.10)
    per_id = result.data.group_by(PROVENANCE_COLUMN).len()
    assert per_id.filter(pl.col("len") == 2).height == 10
    assert per_id["len"].max() == 2


def test_duplicate_copies_share_id_with_new_occurrence_and_ingest_time() -> None:
    frame = _replayed(20)

    result = DuplicateIngestion().apply(frame, severity=0.25, seed=7)

    duplicated_ids = (
        result.data.group_by(PROVENANCE_COLUMN)
        .len()
        .filter(pl.col("len") == 2)[PROVENANCE_COLUMN]
        .to_list()
    )
    copies = result.data.filter(
        pl.col(PROVENANCE_COLUMN).is_in(duplicated_ids) & (pl.col(OCCURRENCE_COLUMN) == 1)
    )
    originals = result.data.filter(
        pl.col(PROVENANCE_COLUMN).is_in(duplicated_ids) & (pl.col(OCCURRENCE_COLUMN) == 0)
    )
    assert copies.height == 5
    assert originals.height == 5
    pairs = copies.select([PROVENANCE_COLUMN, INGEST_TIME]).join(
        originals.select([PROVENANCE_COLUMN, INGEST_TIME]),
        on=PROVENANCE_COLUMN,
        suffix="_original",
    )
    assert (pairs[INGEST_TIME] > pairs[f"{INGEST_TIME}_original"]).all()


def test_duplicate_is_deterministic() -> None:
    frame = _replayed()

    first = DuplicateIngestion().apply(frame, severity=0.1, seed=7)
    second = DuplicateIngestion().apply(frame, severity=0.1, seed=7)

    assert first.data.equals(second.data)


def test_duplicate_requires_replay_and_handles_zero() -> None:
    frame = _replayed()

    with pytest.raises(ValueError, match="run replay first"):
        DuplicateIngestion().apply(frame.drop(INGEST_TIME), severity=0.1, seed=7)

    result = DuplicateIngestion().apply(frame, severity=0.0, seed=7)
    assert result.data.equals(frame)
    assert result.affected_rows == 0
