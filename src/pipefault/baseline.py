"""Clean TLC ETA baseline: LightGBM plus naive reference models."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import structlog

from pipefault.config import Settings
from pipefault.data.manifest import verify_manifest
from pipefault.features.tlc import (
    CATEGORICAL_FEATURES,
    DEFAULT_SIZES,
    EXCLUDED_POST_PICKUP,
    FEATURES,
    TARGET,
    prepare_tlc,
    to_xy,
)

log = structlog.get_logger(__name__)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """RMSE, MAE, and R2 without pulling sklearn into the core install."""
    truth = np.asarray(y_true, dtype=np.float64)
    prediction = np.asarray(y_pred, dtype=np.float64)
    residual = truth - prediction
    mse = float(np.mean(residual**2))
    centered = truth - truth.mean()
    total = float(np.sum(centered**2))
    r2 = 1.0 - float(np.sum(residual**2)) / total if total else float("nan")
    return {
        "rmse": mse**0.5,
        "mae": float(np.mean(np.abs(residual))),
        "r2": r2,
        "n": float(truth.size),
    }


def _zone_median(train: pl.DataFrame, frame: pl.DataFrame, fallback: float) -> np.ndarray:
    medians = train.group_by("PULocationID").agg(pl.col(TARGET).median().alias("_zone_median"))
    aligned = (
        frame.select(["PULocationID"])
        .join(medians, on="PULocationID", how="left")
        .select(pl.col("_zone_median").fill_null(fallback))
    )
    return aligned.to_numpy().ravel().astype(np.float64)


def train_lightgbm(
    X_train: Any,
    y_train: np.ndarray,
    X_val: Any,
    y_val: np.ndarray,
    *,
    seed: int,
    num_boost_round: int,
) -> Any:
    try:
        import lightgbm as lgb
    except ImportError as exc:
        raise RuntimeError("LightGBM is not installed. Run: uv sync --extra ml") from exc

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=num_boost_round,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=50,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=8,
        max_bin=63,
        force_col_wise=True,
        verbose=-1,
    )
    model.fit(
        X_train,
        y_train,
        eval_X=X_val,
        eval_y=y_val,
        eval_metric="rmse",
        categorical_feature=list(CATEGORICAL_FEATURES),
        callbacks=[
            lgb.early_stopping(100, verbose=False),
            lgb.log_evaluation(0),
        ],
    )
    return model


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def _log_mlflow(
    settings: Settings,
    payload: dict[str, Any],
    model: Any,
    *,
    seed: int,
) -> str:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    try:
        import mlflow
        import mlflow.lightgbm
    except ImportError as exc:
        raise RuntimeError("MLflow is not installed. Run: uv sync --extra ml") from exc

    database = settings.mlflow_db.resolve()
    mlflow.set_tracking_uri(f"sqlite:///{database.as_posix()}")
    mlflow.set_experiment("pipefault-baseline")

    with mlflow.start_run(run_name=f"tlc-lightgbm-seed-{seed}") as run:
        mlflow.log_params(payload["params"])
        flat: dict[str, float] = {}
        for split, models in payload["metrics"].items():
            for model_name, metrics in models.items():
                for key, value in metrics.items():
                    flat[f"{split}_{model_name}_{key}"] = value
        mlflow.log_metrics(flat)
        mlflow.log_dict(payload, "run.json")
        mlflow.lightgbm.log_model(model, name="model")
        mlflow.set_tags(
            {
                "dataset": "tlc",
                "task": "eta-regression",
                "git_commit": _git_commit(),
                "features": ",".join(FEATURES),
            }
        )
        return str(run.info.run_id)


def _write_artifacts(settings: Settings, payload: dict[str, Any], model: Any) -> Path:
    out = settings.artifacts_dir / "baseline"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tlc.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    model.booster_.save_model(str(out / "tlc_model.txt"))
    return out


def run_tlc_baseline(
    settings: Settings,
    *,
    seed: int = 42,
    sizes: dict[str, int] | None = None,
    num_boost_round: int = 2000,
    mlflow_enabled: bool = True,
    verify_data: bool = True,
) -> dict[str, Any]:
    """Train and evaluate the clean TLC baseline. Returns the run record."""
    sizes = sizes or dict(DEFAULT_SIZES)
    if any(value <= 0 for value in sizes.values()):
        raise ValueError("Split sizes must be positive")

    if verify_data:
        if not settings.manifest_path.exists():
            raise FileNotFoundError(
                f"No data manifest at {settings.manifest_path}. Run: pipefault data download"
            )
        bad = verify_manifest(settings.manifest_path, settings.data_dir)
        if bad:
            raise RuntimeError("Data manifest mismatch for: " + ", ".join(bad))

    started = time.perf_counter()
    prepared = prepare_tlc(settings.raw_dir, seed=seed, sizes=sizes)
    log.info(
        "baseline.prepared",
        raw_rows=prepared.raw_rows,
        clean_rows=prepared.clean_rows,
        rows={name: frame.height for name, frame in prepared.splits.items()},
    )

    X_train, y_train = to_xy(prepared.splits["train"])
    X_val, y_val = to_xy(prepared.splits["validation"])
    X_test, y_test = to_xy(prepared.splits["test"])
    median_value = prepared.splits["train"][TARGET].median()
    if not isinstance(median_value, (int, float)):
        raise RuntimeError("Training target has no numeric median")
    global_median = float(median_value)

    train_started = time.perf_counter()
    model = train_lightgbm(
        X_train,
        y_train,
        X_val,
        y_val,
        seed=seed,
        num_boost_round=num_boost_round,
    )
    train_seconds = time.perf_counter() - train_started

    metrics: dict[str, dict[str, dict[str, float]]] = {}
    for split_name, X, y in (
        ("validation", X_val, y_val),
        ("test", X_test, y_test),
    ):
        frame = prepared.splits[split_name]
        metrics[split_name] = {
            "global_median": regression_metrics(y, np.full(y.shape, global_median)),
            "zone_median": regression_metrics(
                y, _zone_median(prepared.splits["train"], frame, global_median)
            ),
            "lightgbm": regression_metrics(y, model.predict(X)),
        }

    best_iteration = int(model.booster_.current_iteration())
    elapsed = time.perf_counter() - started
    payload: dict[str, Any] = {
        "dataset": "tlc",
        "task": "eta-regression",
        "created_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "features": list(FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "excluded_post_pickup": list(EXCLUDED_POST_PICKUP),
        "rows": {name: frame.height for name, frame in prepared.splits.items()},
        "raw_rows": prepared.raw_rows,
        "clean_rows": prepared.clean_rows,
        "params": {
            "seed": seed,
            "num_boost_round": num_boost_round,
            "learning_rate": 0.05,
            "num_leaves": 63,
            "min_child_samples": 50,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_lambda": 1.0,
            "max_bin": 63,
            "n_jobs": 8,
            "train_size": sizes["train"],
            "validation_size": sizes["validation"],
            "test_size": sizes["test"],
        },
        "best_iteration": best_iteration,
        "timings": {
            "train_seconds": train_seconds,
            "total_seconds": elapsed,
        },
        "metrics": metrics,
        "mlflow_run_id": None,
    }

    artifacts = _write_artifacts(settings, payload, model)
    payload["artifacts_dir"] = str(artifacts)

    if mlflow_enabled:
        payload["mlflow_run_id"] = _log_mlflow(settings, payload, model, seed=seed)
        # Keep the local record even if tracking is unavailable; refresh it
        # with the run ID after a successful MLflow write.
        (artifacts / "tlc.json").write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
    log.info(
        "baseline.done",
        best_iteration=best_iteration,
        train_seconds=round(train_seconds, 2),
        total_seconds=round(elapsed, 2),
        artifacts=str(artifacts),
    )
    return payload
