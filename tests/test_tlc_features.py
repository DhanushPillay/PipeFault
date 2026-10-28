from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import polars as pl

from pipefault.features.tlc import (
    EXCLUDED_POST_PICKUP,
    FEATURES,
    TARGET,
    add_prior_day_stats,
    clean_tlc,
    prepare_tlc,
    sample_by_hash,
)


def _raw_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "VendorID": [1, 1, 1, 1, 2],
            "tpep_pickup_datetime": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 1, 11, 0),
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 1, 13, 0),
                datetime(2023, 12, 31, 23, 0),
            ],
            "tpep_dropoff_datetime": [
                datetime(2024, 1, 1, 10, 20),
                datetime(2024, 1, 1, 11, 0),
                datetime(2024, 1, 1, 12, 20),
                datetime(2024, 1, 1, 13, 20),
                datetime(2024, 1, 1, 0, 0),
            ],
            "passenger_count": [1, 1, 1, 1, 1],
            "trip_distance": [1.0, 1.0, 0.0, 1.0, 1.0],
            "PULocationID": [1, 1, 1, 300, 1],
            "DOLocationID": [2, 2, 2, 2, 2],
            "fare_amount": [10.0, 10.0, 10.0, 10.0, 10.0],
            "total_amount": [12.0, 12.0, 12.0, 12.0, 12.0],
        }
    )


def test_clean_tlc_drops_invalid_rows_and_keeps_valid_trip() -> None:
    cleaned = clean_tlc(_raw_frame())

    assert cleaned.height == 1
    assert cleaned[TARGET].to_list() == [20.0]
    assert cleaned["pickup_hour"].to_list() == [10]
    assert cleaned["pickup_month"].to_list() == [1]


def test_prior_day_stats_use_strictly_earlier_days() -> None:
    daily = pl.DataFrame(
        {
            "zone_id": [1, 1, 1, 2],
            "pickup_date": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 1),
            ],
            "duration_sum": [10.0, 30.0, 50.0, 7.0],
            "trip_count": [1, 1, 1, 1],
        }
    )

    stats = add_prior_day_stats(daily).sort(["zone_id", "pickup_date"])

    assert stats["zone_avg_duration_prior"].to_list() == [
        None,
        10.0,
        20.0,
        None,
    ]
    assert stats["zone_trip_count_prior"].to_list() == [None, 1.0, 2.0, None]


def test_features_exclude_post_pickup_columns() -> None:
    assert set(FEATURES).isdisjoint(EXCLUDED_POST_PICKUP)
    assert TARGET not in FEATURES
    assert "tpep_dropoff_datetime" in EXCLUDED_POST_PICKUP
    assert "trip_distance" in EXCLUDED_POST_PICKUP


def test_hash_sample_is_deterministic() -> None:
    frame = pl.DataFrame(
        {
            "tpep_pickup_datetime": [datetime(2024, 1, 1, 0, minute % 60) for minute in range(100)],
            "tpep_dropoff_datetime": [
                datetime(2024, 1, 1, 1, minute % 60) for minute in range(100)
            ],
            "PULocationID": [1] * 100,
            "DOLocationID": [2] * 100,
            "VendorID": [1] * 100,
            "passenger_count": [1] * 100,
            "trip_distance": [1.0] * 100,
            "fare_amount": [10.0] * 100,
            "total_amount": [12.0] * 100,
        }
    )

    first = sample_by_hash(frame, 10, seed=42)
    second = sample_by_hash(frame, 10, seed=42)

    assert first.height == 10
    assert first.equals(second)


def _monthly_frame(month: int, outside: datetime) -> pl.DataFrame:
    inside = datetime(2024, month, 15, 10, 0)
    return pl.DataFrame(
        {
            "VendorID": [1, 1],
            "tpep_pickup_datetime": [inside, outside],
            "tpep_dropoff_datetime": [
                inside.replace(minute=15),
                outside.replace(minute=10),
            ],
            "passenger_count": [1, 1],
            "trip_distance": [1.0, 1.0],
            "PULocationID": [1, 1],
            "DOLocationID": [2, 2],
            "fare_amount": [10.0, 10.0],
            "total_amount": [12.0, 12.0],
        }
    )


def test_prepare_tlc_drops_rows_outside_file_month(tmp_path: Path) -> None:
    raw = tmp_path / "tlc"
    raw.mkdir()
    for month, outside in (
        (1, datetime(2024, 2, 1, 0, 0)),
        (7, datetime(2024, 8, 1, 0, 0)),
        (10, datetime(2024, 11, 1, 0, 0)),
    ):
        _monthly_frame(month, outside).write_parquet(
            raw / f"yellow_tripdata_2024-{month:02d}.parquet"
        )

    prepared = prepare_tlc(
        tmp_path,
        seed=7,
        sizes={"train": 6, "validation": 3, "test": 3},
    )

    assert prepared.raw_rows == 6
    assert prepared.clean_rows == 3
    assert prepared.splits["train"]["pickup_month"].to_list() == [1]
    assert prepared.splits["validation"]["pickup_month"].to_list() == [7]
    assert prepared.splits["test"]["pickup_month"].to_list() == [10]
    assert prepared.splits["train"]["pickup_date"].to_list() == [date(2024, 1, 15)]
