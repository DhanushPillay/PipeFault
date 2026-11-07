from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import structlog

from pipefault.config import Settings

log = structlog.get_logger(__name__)

RETAIL_COLUMN_MAP = {
    "Invoice": "InvoiceNo",
    "Price": "UnitPrice",
    "Customer ID": "CustomerID",
}

TLC_COUNT_KEYS = (
    "rows",
    "duplicate_rows",
    "invalid_duration",
    "invalid_distance",
    "negative_fare",
    "invalid_pu_zone",
    "invalid_do_zone",
    "passenger_count_zero",
)

MOVIELENS_VALID_RATINGS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
MOVIELENS_RELEASE = datetime(2023, 10, 14)


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _sum(frame: pl.DataFrame, expression: pl.Expr) -> int:
    return int(frame.select(expression.sum()).item())


def _nulls(frame: pl.DataFrame) -> dict[str, int]:
    return {
        name: int(frame.select(pl.col(name).is_null().sum()).item())
        for name in frame.columns
    }


def _min_iso(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _max_iso(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def audit_tlc_frame(frame: pl.DataFrame) -> dict[str, Any]:
    """Natural-defect metrics for one TLC parquet file."""
    duration = (
        pl.col("tpep_dropoff_datetime") - pl.col("tpep_pickup_datetime")
    ).dt.total_minutes()
    return {
        "rows": frame.height,
        "columns": frame.width,
        "pickup_min": _iso(frame.select(pl.col("tpep_pickup_datetime").min()).item()),
        "pickup_max": _iso(frame.select(pl.col("tpep_pickup_datetime").max()).item()),
        "dropoff_min": _iso(frame.select(pl.col("tpep_dropoff_datetime").min()).item()),
        "dropoff_max": _iso(frame.select(pl.col("tpep_dropoff_datetime").max()).item()),
        "null_counts": _nulls(frame),
        "duplicate_rows": int(frame.is_duplicated().sum()),
        "invalid_duration": _sum(frame, (duration <= 0) | (duration > 180)),
        "invalid_distance": _sum(frame, pl.col("trip_distance") <= 0),
        "negative_fare": _sum(frame, pl.col("fare_amount") < 0),
        "invalid_pu_zone": _sum(frame, ~pl.col("PULocationID").is_between(1, 263)),
        "invalid_do_zone": _sum(frame, ~pl.col("DOLocationID").is_between(1, 263)),
        "passenger_count_zero": _sum(frame, pl.col("passenger_count") == 0),
    }


def audit_tlc(raw_dir: Path) -> dict[str, Any]:
    files = sorted((raw_dir / "tlc").glob("yellow_tripdata_2024-*.parquet"))
    if not files:
        return {
            "status": "missing",
            "hint": "pipefault data download --dataset tlc",
        }

    totals = {key: 0 for key in TLC_COUNT_KEYS}
    nulls: dict[str, int] = {}
    pickup_min: str | None = None
    pickup_max: str | None = None
    dropoff_min: str | None = None
    dropoff_max: str | None = None
    per_file: list[dict[str, Any]] = []
    columns = 0

    for path in files:
        frame = pl.read_parquet(path)
        metrics = audit_tlc_frame(frame)
        per_file.append({"file": path.name, "rows": metrics["rows"]})
        columns = metrics["columns"]
        for key in TLC_COUNT_KEYS:
            totals[key] += int(metrics[key])
        for name, count in metrics["null_counts"].items():
            nulls[name] = nulls.get(name, 0) + int(count)
        pickup_min = _min_iso(pickup_min, metrics["pickup_min"])
        pickup_max = _max_iso(pickup_max, metrics["pickup_max"])
        dropoff_min = _min_iso(dropoff_min, metrics["dropoff_min"])
        dropoff_max = _max_iso(dropoff_max, metrics["dropoff_max"])

    return {
        "status": "ok",
        "files": per_file,
        "columns": columns,
        **totals,
        "null_counts": nulls,
        "pickup_min": pickup_min,
        "pickup_max": pickup_max,
        "dropoff_min": dropoff_min,
        "dropoff_max": dropoff_max,
    }


def audit_movielens_frame(
    ratings: pl.DataFrame,
    movies: pl.DataFrame,
    tags: pl.DataFrame,
) -> dict[str, Any]:
    """Natural-defect metrics for the MovieLens 32M tables."""
    known_movies = movies.select("movieId").unique()
    event_time = (pl.col("timestamp") * 1000).cast(pl.Datetime("ms"))
    return {
        "rows": ratings.height,
        "columns": ratings.width,
        "users": int(ratings["userId"].n_unique()),
        "movies_rated": int(ratings["movieId"].n_unique()),
        "rating_min": ratings.select(pl.col("rating").min()).item(),
        "rating_max": ratings.select(pl.col("rating").max()).item(),
        "rating_null": _sum(ratings, pl.col("rating").is_null()),
        "timestamp_min": _iso(ratings.select(event_time.min()).item()),
        "timestamp_max": _iso(ratings.select(event_time.max()).item()),
        "duplicate_user_movie": int(
            ratings.select(["userId", "movieId"]).is_duplicated().sum()
        ),
        "invalid_rating": _sum(
            ratings,
            pl.col("rating").is_null() | ~pl.col("rating").is_in(MOVIELENS_VALID_RATINGS),
        ),
        "unknown_movie": ratings.join(
            known_movies, on="movieId", how="anti"
        ).height,
        "future_timestamp": _sum(
            ratings,
            event_time > MOVIELENS_RELEASE,
        ),
        "duplicate_rows": int(ratings.is_duplicated().sum()),
        "rating_distribution": ratings.group_by("rating")
        .len()
        .sort("rating")
        .to_dicts(),
        "movies": {
            "rows": movies.height,
            "duplicate_movie_ids": int(movies["movieId"].is_duplicated().sum()),
            "missing_genres": _sum(
                movies,
                pl.col("genres").is_null() | (pl.col("genres") == "(no genres listed)"),
            ),
            "movies_without_ratings": movies.join(
                ratings.select("movieId").unique(), on="movieId", how="anti"
            ).height,
        },
        "tags": {
            "rows": tags.height,
            "movies_tagged": int(tags["movieId"].n_unique()),
            "null_tags": _sum(tags, pl.col("tag").is_null()),
            "orphan_tags": tags.join(
                known_movies, on="movieId", how="anti"
            ).height,
            "duplicate_tags": int(tags.is_duplicated().sum()),
        },
    }


def audit_movielens(raw_dir: Path) -> dict[str, Any]:
    base = raw_dir / "movielens"
    ratings_path = base / "ratings.csv"
    movies_path = base / "movies.csv"
    tags_path = base / "tags.csv"
    if not all(path.exists() for path in (ratings_path, movies_path, tags_path)):
        return {
            "status": "missing",
            "hint": "pipefault data download --dataset movielens",
        }

    ratings = pl.read_csv(
        ratings_path,
        schema_overrides={
            "userId": pl.Int32,
            "movieId": pl.Int32,
            "rating": pl.Float32,
            "timestamp": pl.Int64,
        },
    )
    movies = pl.read_csv(
        movies_path,
        schema_overrides={
            "movieId": pl.Int32,
            "title": pl.String,
            "genres": pl.String,
        },
    )
    tags = pl.read_csv(
        tags_path,
        schema_overrides={
            "userId": pl.Int32,
            "movieId": pl.Int32,
            "tag": pl.String,
            "timestamp": pl.Int64,
        },
    )
    return {
        "status": "ok",
        "files": {
            "ratings": ratings_path.name,
            "movies": movies_path.name,
            "tags": tags_path.name,
        },
        **audit_movielens_frame(ratings, movies, tags),
    }


def audit_retail_frame(frame: pl.DataFrame) -> dict[str, Any]:
    """Natural-defect metrics for the combined Online Retail II workbook."""
    if "sheet" in frame.columns:
        frame = frame.drop("sheet")
    if frame.schema.get("InvoiceDate") == pl.String:
        frame = frame.with_columns(
            pl.col("InvoiceDate").str.to_datetime(strict=False)
        )
    invoice_no = pl.col("InvoiceNo").cast(pl.String)
    return {
        "rows": frame.height,
        "columns": frame.width,
        "date_min": _iso(frame.select(pl.col("InvoiceDate").min()).item()),
        "date_max": _iso(frame.select(pl.col("InvoiceDate").max()).item()),
        "missing_customer_id": _sum(frame, pl.col("CustomerID").is_null()),
        "missing_description": _sum(frame, pl.col("Description").is_null()),
        "negative_quantity": _sum(frame, pl.col("Quantity") < 0),
        "nonpositive_price": _sum(frame, pl.col("UnitPrice") <= 0),
        "cancellations": _sum(frame, invoice_no.str.starts_with("C")),
        "duplicate_rows": int(frame.is_duplicated().sum()),
        "top_countries": frame.group_by("Country")
        .len()
        .sort("len", descending=True)
        .head(5)
        .to_dicts(),
    }


def _normalize_retail_sheet(sheet: pd.DataFrame) -> pl.DataFrame:
    """Normalize mixed Excel types before converting to Polars.

    The workbook stores cancellation invoices as strings and regular invoices
    as numbers, so pandas infers an object column that Polars cannot cast
    consistently without an explicit pass.
    """
    normalized = sheet.rename(columns=RETAIL_COLUMN_MAP).copy()
    for column in ("InvoiceNo", "StockCode", "Description", "Country"):
        if column in normalized.columns:
            normalized[column] = normalized[column].astype("string")
    for column in ("Quantity", "UnitPrice", "CustomerID"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if "InvoiceDate" in normalized.columns:
        normalized["InvoiceDate"] = pd.to_datetime(
            normalized["InvoiceDate"], errors="coerce"
        )
    return pl.from_pandas(normalized)


def audit_retail(raw_dir: Path) -> dict[str, Any]:
    workbook = raw_dir / "retail" / "online_retail_II.xlsx"
    if not workbook.exists():
        return {
            "status": "missing",
            "hint": "pipefault data download --dataset retail",
        }

    sheets = pd.read_excel(workbook, sheet_name=None)
    frames: list[pl.DataFrame] = []
    for name, sheet in sheets.items():
        frame = _normalize_retail_sheet(sheet)
        frames.append(frame.with_columns(pl.lit(name).alias("sheet")))
    combined = pl.concat(frames, how="vertical_relaxed")
    return {
        "status": "ok",
        "sheets": list(sheets),
        **audit_retail_frame(combined),
    }


def audit_dataset(name: str, raw_dir: Path) -> dict[str, Any]:
    if name == "tlc":
        return audit_tlc(raw_dir)
    if name == "movielens":
        return audit_movielens(raw_dir)
    if name == "retail":
        return audit_retail(raw_dir)
    raise ValueError(f"unknown dataset: {name}")


def audit_datasets(
    names: Iterable[str], settings: Settings
) -> dict[str, dict[str, Any]]:
    results = {name: audit_dataset(name, settings.raw_dir) for name in names}
    settings.audit_dir.mkdir(parents=True, exist_ok=True)
    for name, result in results.items():
        path = settings.audit_dir / f"{name}.json"
        path.write_text(
            json.dumps(result, indent=2, default=str),
            encoding="utf-8",
        )
        log.info("audit.written", dataset=name, path=str(path))
    return results
