"""Generate a tiny deterministic TLC-shaped fixture for CI smoke tests."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "total_amount",
]


def make_month(year: int, month: int, rows: int, rng: np.random.Generator) -> pl.DataFrame:
    days_in_month = 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31
    pickup_days = rng.integers(1, days_in_month + 1, size=rows)
    pickup_hours = rng.integers(0, 24, size=rows)
    pickup_minutes = rng.integers(0, 60, size=rows)
    pickups = [
        datetime(year, month, int(d), int(h), int(m))
        for d, h, m in zip(pickup_days, pickup_hours, pickup_minutes, strict=True)
    ]
    durations = rng.integers(5, 45, size=rows)
    dropoffs = [p + timedelta(minutes=int(d)) for p, d in zip(pickups, durations, strict=True)]
    return pl.DataFrame(
        {
            "VendorID": rng.choice([1, 2], size=rows).astype(np.int64),
            "tpep_pickup_datetime": pickups,
            "tpep_dropoff_datetime": dropoffs,
            "passenger_count": rng.integers(1, 5, size=rows).astype(np.int64),
            "trip_distance": rng.uniform(0.5, 12.0, size=rows),
            "PULocationID": rng.integers(1, 264, size=rows).astype(np.int64),
            "DOLocationID": rng.integers(1, 264, size=rows).astype(np.int64),
            "fare_amount": rng.uniform(3.0, 40.0, size=rows),
            "total_amount": rng.uniform(5.0, 50.0, size=rows),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tests/fixtures")
    parser.add_argument("--rows-per-month", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = Path(args.out) / "raw" / "tlc"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    for month in range(1, 13):
        frame = make_month(2024, month, args.rows_per_month, rng)
        path = out / f"yellow_tripdata_2024-{month:02d}.parquet"
        frame.write_parquet(path)
    print(f"Wrote 12 monthly parquets to {out}")


if __name__ == "__main__":
    main()
