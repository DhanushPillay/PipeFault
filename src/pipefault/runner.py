"""Paired clean/defect runs over the TLC pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from pipefault.baseline import regression_metrics, train_lightgbm
from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN
from pipefault.features.tlc import TARGET, PreparedTlc, to_xy
from pipefault.inject.base import derive_seed
from pipefault.inject.qc import verify_injection
from pipefault.inject.registry import get as get_injector
from pipefault.records import RunRecord, config_hash
from pipefault.runstore import RunStore
from pipefault.simulate.replay import ReplaySpec, apply_watermark, replay

TIME_COLUMN = "tpep_pickup_datetime"
SPLITS = ("train", "validation", "test")
MODELS = ("lightgbm",)


@dataclass(frozen=True)
class RunSpec:
    """One condition: dataset, model, seed, and optional defect treatment."""

    dataset: str = "tlc"
    model: str = "lightgbm"
    seed: int = 42
    num_boost_round: int = 50
    allowed_lateness_seconds: int = 3600
    defect: str | None = None
    severity: float = 0.0

    def __post_init__(self) -> None:
        if self.model not in MODELS:
            raise ValueError(f"model must be one of {list(MODELS)}")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.num_boost_round <= 0:
            raise ValueError("num_boost_round must be positive")
        if self.allowed_lateness_seconds <= 0:
            raise ValueError("allowed_lateness_seconds must be positive")
        if self.defect is None:
            if self.severity != 0.0:
                raise ValueError("severity must be 0 for a clean run")
        elif not 0.0 < self.severity <= 1.0:
            raise ValueError("defect severity must be in (0, 1]")

    @property
    def run_id(self) -> str:
        label = "clean" if self.defect is None else f"{self.defect.upper()}-s{self.severity:g}"
        return f"{self.dataset}-{label}-{self.model}-seed{self.seed}"


@dataclass(frozen=True)
class ConditionResult:
    record: RunRecord
    predictions: dict[str, pl.DataFrame]


def prepare_for_run(
    prepared: PreparedTlc,
    *,
    seed: int = 42,
    allowed_lateness_seconds: int = 3600,
) -> PreparedTlc:
    """Replay event time and drop events that miss the watermark."""
    spec = ReplaySpec(
        time_column=TIME_COLUMN,
        allowed_lateness_seconds=allowed_lateness_seconds,
        seed=seed,
    )
    splits: dict[str, pl.DataFrame] = {}
    for name, frame in prepared.splits.items():
        kept, _ = apply_watermark(
            replay(frame, spec), allowed_lateness_seconds=allowed_lateness_seconds
        )
        splits[name] = kept
    return PreparedTlc(
        splits=splits,
        raw_rows=prepared.raw_rows,
        clean_rows=prepared.clean_rows,
        files=prepared.files,
    )


def _predict(model: Any, frame: pl.DataFrame) -> pl.DataFrame:
    features, _ = to_xy(frame)
    yhat = np.asarray(model.predict(features), dtype=np.float64)
    return frame.select(
        [
            pl.col(PROVENANCE_COLUMN),
            pl.col(OCCURRENCE_COLUMN),
            pl.col("pickup_date").cast(pl.String).alias("batch_id"),
            pl.col(TARGET).cast(pl.Float64).alias("y"),
        ]
    ).with_columns(pl.Series("yhat", yhat))


def _inject(
    splits: dict[str, pl.DataFrame], *, defect: str, severity: float, seed: int
) -> tuple[dict[str, pl.DataFrame], dict[str, Any]]:
    injector = get_injector(defect)
    injected: dict[str, pl.DataFrame] = {}
    per_split: dict[str, Any] = {}
    for name, frame in splits.items():
        result = injector.apply(frame, severity=severity, seed=seed)
        verify_injection(frame, result)
        injected[name] = result.data
        per_split[name] = {
            "realized_severity": result.realized_severity,
            "affected_units": result.affected_units,
            "affected_rows": result.affected_rows,
            "details": result.details,
        }
    return injected, per_split


def run_condition(
    prepared: PreparedTlc,
    artifacts_dir: Path,
    spec: RunSpec,
    *,
    force: bool = False,
) -> ConditionResult:
    """Run one clean or injected condition, reusing a completed record."""
    store = RunStore(artifacts_dir / "runs")
    prediction_dir = artifacts_dir / "predictions" / spec.run_id
    if not store.should_run(spec.run_id, force=force):
        predictions = {
            name: pl.read_parquet(prediction_dir / f"{name}.parquet")
            for name in SPLITS
            if (prediction_dir / f"{name}.parquet").exists()
        }
        return ConditionResult(store.load(spec.run_id), predictions)

    splits = prepared.splits
    metadata: dict[str, Any] = {
        "defect": spec.defect,
        "severity": spec.severity,
        "allowed_lateness_seconds": spec.allowed_lateness_seconds,
        "rows": {name: frame.height for name, frame in splits.items()},
    }
    if spec.defect is not None:
        inject_seed = derive_seed(
            spec.seed, defect=spec.defect, severity=spec.severity, purpose="inject"
        )
        splits, per_split = _inject(
            splits, defect=spec.defect, severity=spec.severity, seed=inject_seed
        )
        metadata["injection"] = per_split

    X_train, y_train = to_xy(splits["train"])
    X_val, y_val = to_xy(splits["validation"])
    model = train_lightgbm(
        X_train,
        y_train,
        X_val,
        y_val,
        seed=spec.seed,
        num_boost_round=spec.num_boost_round,
    )
    predictions = {name: _predict(model, frame) for name, frame in splits.items()}

    metrics: dict[str, float] = {}
    for name, frame in predictions.items():
        for key, value in regression_metrics(
            frame["y"].to_numpy(), frame["yhat"].to_numpy()
        ).items():
            metrics[f"{name}_{key}"] = value

    prediction_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in predictions.items():
        frame.write_parquet(prediction_dir / f"{name}.parquet")

    record = RunRecord(
        run_id=spec.run_id,
        dataset=spec.dataset,
        task="eta-regression",
        model=spec.model,
        seed=spec.seed,
        config_hash=config_hash(asdict(spec)),
        status="completed",
        metrics=metrics,
        created_at=datetime.now(UTC).isoformat(),
        metadata=metadata,
    )
    store.save(record, force=force)
    return ConditionResult(record, predictions)


def run_pair(
    prepared: PreparedTlc,
    artifacts_dir: Path,
    *,
    defect: str,
    severity: float,
    seed: int = 42,
    num_boost_round: int = 50,
    allowed_lateness_seconds: int = 3600,
    force: bool = False,
) -> tuple[ConditionResult, ConditionResult]:
    """Run the clean reference and one injected condition on shared rows."""
    replayed = prepare_for_run(
        prepared, seed=seed, allowed_lateness_seconds=allowed_lateness_seconds
    )
    clean_spec = RunSpec(
        seed=seed,
        num_boost_round=num_boost_round,
        allowed_lateness_seconds=allowed_lateness_seconds,
    )
    defect_spec = RunSpec(
        seed=seed,
        num_boost_round=num_boost_round,
        allowed_lateness_seconds=allowed_lateness_seconds,
        defect=defect,
        severity=severity,
    )
    clean = run_condition(replayed, artifacts_dir, clean_spec, force=force)
    injected = run_condition(replayed, artifacts_dir, defect_spec, force=force)
    return clean, injected
