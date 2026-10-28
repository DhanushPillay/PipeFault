"""Clean TLC ETA features with strictly prior-day zone statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import polars as pl
import structlog

log = structlog.get_logger(__name__)

TARGET: Final = "duration_min"

FEATURES: Final = (
    "VendorID",
    "pickup_hour",
    "pickup_dow",
    "pickup_month",
    "passenger_count",
    "PULocationID",
    "DOLocationID",
    "zone_avg_duration_prior",
    "zone_trip_count_prior",
)

CATEGORICAL_FEATURES: Final = ("VendorID", "PULocationID", "DOLocationID")

EXCLUDED_POST_PICKUP: Final = (
    "tpep_dropoff_datetime",
    "trip_distance",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "Airport_fee",
    "store_and_fwd_flag",
    "RatecodeID",
)

READ_COLUMNS: Final = (
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "total_amount",
)

TRIP_KEY: Final = (
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "VendorID",
    "passenger_count",
    "trip_distance",
    "fare_amount",
    "total_amount",
)

SPLIT_MONTHS: Final = {
    "train": (1, 6),
    "validation": (7, 9),
    "test": (10, 12),
}

# One day is removed from the end of the earlier split in each pair.
EMBARGO_DATES: Final = {
    "train": date(2024, 6, 30),
    "validation": date(2024, 9, 30),
}

DEFAULT_SIZES: Final = {
    "train": 500_000,
    "validation": 150_000,
    "test": 150_000,
}


@dataclass(frozen=True)
class PreparedTlc:
    """Sampled splits plus the row counts needed for the run record."""

    splits: dict[str, pl.DataFrame]
    raw_rows: int
    clean_rows: int
    files: tuple[str, ...]


def tlc_files(raw_dir: Path) -> list[Path]:
    files = sorted((raw_dir / "tlc").glob("yellow_tripdata_2024-*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No TLC 2024 parquet files under {raw_dir / 'tlc'}. "
            "Run: pipefault data download --dataset tlc"
        )
    return files


def clean_tlc(frame: pl.DataFrame) -> pl.DataFrame:
    """Apply the preregistered cleaning rules and add time features."""
    duration = (pl.col("tpep_dropoff_datetime") - pl.col("tpep_pickup_datetime")).dt.total_minutes()
    return (
        frame.with_columns(duration.alias(TARGET))
        .filter(
            (pl.col("tpep_pickup_datetime").dt.year() == 2024)
            & (pl.col("tpep_dropoff_datetime").dt.year() == 2024)
            & pl.col(TARGET).is_between(1, 180)
            & (pl.col("trip_distance") > 0)
            & (pl.col("fare_amount") >= 0)
            & (pl.col("total_amount") >= 0)
            & pl.col("PULocationID").is_between(1, 263)
            & pl.col("DOLocationID").is_between(1, 263)
            & (pl.col("passenger_count").is_null() | pl.col("passenger_count").is_between(0, 6))
        )
        .with_columns(
            pl.col("tpep_pickup_datetime").dt.date().alias("pickup_date"),
            pl.col("tpep_pickup_datetime").dt.hour().cast(pl.Int8).alias("pickup_hour"),
            pl.col("tpep_pickup_datetime").dt.weekday().cast(pl.Int8).alias("pickup_dow"),
            pl.col("tpep_pickup_datetime").dt.month().cast(pl.Int8).alias("pickup_month"),
        )
    )


def add_prior_day_stats(daily: pl.DataFrame) -> pl.DataFrame:
    """Turn daily zone aggregates into statistics from earlier days only.

    The returned row for date ``D`` uses trips from dates strictly before ``D``.
    The first day for each zone is null rather than a fabricated zero.
    """
    ordered = daily.sort(["zone_id", "pickup_date"])
    with_prior = ordered.with_columns(
        pl.col("duration_sum")
        .cum_sum()
        .shift(1)
        .over("zone_id", order_by="pickup_date")
        .alias("_prior_duration"),
        pl.col("trip_count")
        .cum_sum()
        .shift(1)
        .over("zone_id", order_by="pickup_date")
        .alias("_prior_trips"),
    )
    return with_prior.with_columns(
        pl.when(pl.col("_prior_trips") > 0)
        .then(pl.col("_prior_duration") / pl.col("_prior_trips"))
        .otherwise(None)
        .cast(pl.Float32)
        .alias("zone_avg_duration_prior"),
        pl.col("_prior_trips").cast(pl.Float32).alias("zone_trip_count_prior"),
    ).select(
        [
            "zone_id",
            "pickup_date",
            "zone_avg_duration_prior",
            "zone_trip_count_prior",
        ]
    )


def sample_by_hash(frame: pl.DataFrame, size: int, *, seed: int) -> pl.DataFrame:
    """Take a deterministic row sample keyed by the trip's stable fields."""
    if frame.height <= size:
        return frame
    return (
        frame.with_columns(pl.struct(list(TRIP_KEY)).hash(seed=seed).alias("_trip_hash"))
        .sort("_trip_hash")
        .head(size)
        .drop("_trip_hash")
    )


def prepare_tlc(
    raw_dir: Path,
    *,
    seed: int = 42,
    sizes: dict[str, int] | None = None,
) -> PreparedTlc:
    """Clean monthly partitions, build prior-day zone stats, and sample splits."""
    sizes = sizes or dict(DEFAULT_SIZES)
    files = tlc_files(raw_dir)
    daily_parts: list[pl.DataFrame] = []
    split_parts: dict[str, list[pl.DataFrame]] = {name: [] for name in SPLIT_MONTHS}
    raw_rows = 0
    clean_rows = 0

    for path in files:
        file_month = int(path.stem.rsplit("-", 1)[-1])
        frame = pl.read_parquet(path, columns=list(READ_COLUMNS))
        raw_height = frame.height
        raw_rows += raw_height
        frame = clean_tlc(frame)
        # A monthly partition must not leak rows into another month's split.
        # Trips whose pickup or dropoff falls outside this file's month are
        # natural timestamp defects and are excluded from the clean baseline.
        frame = frame.filter(
            (pl.col("pickup_month") == file_month)
            & (pl.col("tpep_dropoff_datetime").dt.month() == file_month)
        )
        clean_rows += frame.height
        if frame.is_empty():
            continue

        daily_parts.append(
            frame.group_by(["PULocationID", "pickup_date"])
            .agg(
                pl.col(TARGET).sum().alias("duration_sum"),
                pl.len().cast(pl.UInt32).alias("trip_count"),
            )
            .rename({"PULocationID": "zone_id"})
        )

        for name, (first_month, last_month) in SPLIT_MONTHS.items():
            subset = frame.filter(pl.col("pickup_month").is_between(first_month, last_month))
            embargo = EMBARGO_DATES.get(name)
            if embargo is not None:
                subset = subset.filter(pl.col("pickup_date") != embargo)
            # Cap each file's contribution before concatenation to bound
            # memory. Round up so the exact split size is still reachable;
            # the final hash sample enforces it after all files load.
            months = last_month - first_month + 1
            per_file_cap = max(1, (sizes[name] + months - 1) // months)
            split_parts[name].append(sample_by_hash(subset, per_file_cap, seed=seed))

        log.info(
            "tlc.file",
            file=path.name,
            raw_rows=raw_height,
            clean_rows=frame.height,
        )

    if not daily_parts:
        raise RuntimeError("No TLC rows survived cleaning")

    daily = (
        pl.concat(daily_parts)
        .group_by(["zone_id", "pickup_date"])
        .agg(
            pl.col("duration_sum").sum(),
            pl.col("trip_count").sum(),
        )
    )
    stats = add_prior_day_stats(daily)

    splits: dict[str, pl.DataFrame] = {}
    for name, parts in split_parts.items():
        if not parts:
            raise RuntimeError(f"No rows for split {name}")
        sampled = sample_by_hash(pl.concat(parts), sizes[name], seed=seed)
        splits[name] = sampled.join(
            stats,
            left_on=["PULocationID", "pickup_date"],
            right_on=["zone_id", "pickup_date"],
            how="left",
        )

    return PreparedTlc(
        splits=splits,
        raw_rows=raw_rows,
        clean_rows=clean_rows,
        files=tuple(path.name for path in files),
    )


def to_xy(frame: pl.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Return a pandas feature frame and a float32 target array."""
    data = frame.select([*FEATURES, TARGET]).to_pandas()
    for column in CATEGORICAL_FEATURES:
        data[column] = data[column].astype("category")
    return data[list(FEATURES)], data[TARGET].to_numpy(dtype="float32")
