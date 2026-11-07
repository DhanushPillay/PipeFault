from __future__ import annotations

from datetime import datetime

import polars as pl

from pipefault.data.provenance import (
    OCCURRENCE_COLUMN,
    PROVENANCE_COLUMN,
    add_occurrence,
    add_provenance,
)
from pipefault.features.tlc import clean_tlc, sample_by_hash


def test_same_file_and_row_gets_same_id() -> None:
    frame = pl.DataFrame({"value": [10, 20, 30]})

    first = add_provenance(frame, dataset="tlc", file="yellow_tripdata_2024-01.parquet")
    second = add_provenance(frame, dataset="tlc", file="yellow_tripdata_2024-01.parquet")

    assert first[PROVENANCE_COLUMN].to_list() == second[PROVENANCE_COLUMN].to_list()
    assert first[PROVENANCE_COLUMN].n_unique() == 3


def test_dataset_or_file_change_the_id() -> None:
    frame = pl.DataFrame({"value": [10, 20, 30]})
    base = set(add_provenance(frame, dataset="tlc", file="a.parquet")[PROVENANCE_COLUMN])
    other_file = set(add_provenance(frame, dataset="tlc", file="b.parquet")[PROVENANCE_COLUMN])
    other_dataset = set(
        add_provenance(frame, dataset="movielens", file="a.parquet")[PROVENANCE_COLUMN]
    )

    assert base.isdisjoint(other_file)
    assert base.isdisjoint(other_dataset)


def test_duplicate_rows_share_id_with_distinct_occurrences() -> None:
    frame = add_provenance(
        pl.DataFrame({"value": [10, 20]}),
        dataset="tlc",
        file="a.parquet",
    )

    numbered = add_occurrence(pl.concat([frame, frame]))
    grouped = numbered.group_by(PROVENANCE_COLUMN).agg(
        pl.col(OCCURRENCE_COLUMN).sort().alias("occurrences")
    )

    assert grouped.height == 2
    assert grouped["occurrences"].to_list() == [[0, 1], [0, 1]]


def test_million_rows_have_no_collisions() -> None:
    frame = pl.DataFrame({"value": range(1_000_000)})

    ids = add_provenance(frame, dataset="tlc", file="a.parquet")[PROVENANCE_COLUMN]

    assert ids.n_unique() == 1_000_000


def test_provenance_survives_clean_and_sample() -> None:
    frame = pl.DataFrame(
        {
            "VendorID": [1, 1, 1],
            "tpep_pickup_datetime": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 1, 11, 0),
                datetime(2024, 1, 1, 12, 0),
            ],
            "tpep_dropoff_datetime": [
                datetime(2024, 1, 1, 10, 20),
                datetime(2024, 1, 1, 11, 0),
                datetime(2024, 1, 1, 12, 20),
            ],
            "passenger_count": [1, 1, 1],
            "trip_distance": [1.0, 0.0, 1.0],
            "PULocationID": [1, 1, 300],
            "DOLocationID": [2, 2, 2],
            "fare_amount": [10.0, 10.0, 10.0],
            "total_amount": [12.0, 12.0, 12.0],
        }
    )
    with_id = add_provenance(frame, dataset="tlc", file="a.parquet")
    expected = with_id.slice(0, 1)[PROVENANCE_COLUMN].to_list()

    cleaned = clean_tlc(with_id)
    sampled = sample_by_hash(cleaned, 1, seed=42)

    assert cleaned[PROVENANCE_COLUMN].to_list() == expected
    assert sampled[PROVENANCE_COLUMN].to_list() == expected
