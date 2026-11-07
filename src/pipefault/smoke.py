"""P0 smoke experiment: clean/clean identity and one D5 duplicate condition."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl

from pipefault.baseline import regression_metrics, train_lightgbm
from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN
from pipefault.features.tlc import TARGET, PreparedTlc, prepare_tlc, to_xy
from pipefault.records import RunRecord, config_hash
from pipefault.runstore import RunStore

TAU_MULTIPLIER = 0.1
BETA = 0.0  # PSI/KS arrive in P2; P0 keeps beta fixed at zero.


def duplicate_ingestion(frame: pl.DataFrame, *, severity: float, seed: int) -> pl.DataFrame:
    """Replay an exact fraction of rows with incremented occurrences."""
    if not 0.0 <= severity <= 1.0:
        raise ValueError("severity must be in [0, 1]")
    count = round(severity * frame.height)
    if count == 0:
        return frame
    selected = (
        frame.with_columns(
            pl.struct([pl.col(PROVENANCE_COLUMN)]).hash(seed=seed).alias("_replay_hash")
        )
        .sort("_replay_hash")
        .head(count)
        .drop("_replay_hash")
        .with_columns((pl.col(OCCURRENCE_COLUMN) + 1).cast(pl.UInt32).alias(OCCURRENCE_COLUMN))
    )
    return pl.concat([frame, selected], how="vertical_relaxed")


def annotate_pair(
    clean: dict[str, pl.DataFrame],
    defect: dict[str, pl.DataFrame],
    *,
    split: str = "test",
    tau_multiplier: float = TAU_MULTIPLIER,
) -> dict[str, float | int]:
    """Compute alpha, beta, gamma, and the silence index on matched rows."""
    clean_rows = clean[split]
    defect_rows = defect[split]
    clean_first = clean_rows.unique(subset=[PROVENANCE_COLUMN], keep="first")
    defect_first = defect_rows.unique(subset=[PROVENANCE_COLUMN], keep="first")
    joined = clean_first.select([PROVENANCE_COLUMN, "yhat"]).join(
        defect_first.select([PROVENANCE_COLUMN, "yhat"]),
        on=PROVENANCE_COLUMN,
        how="inner",
        suffix="_defect",
    )
    if joined.height == 0:
        raise ValueError("no matched rows between clean and defect runs")

    tau_pred = tau_multiplier * float(cast(float, clean_first["yhat"].std()))
    moved = (joined["yhat_defect"] - joined["yhat"]).abs() > tau_pred
    alpha = float(cast(float, moved.mean()))
    gamma = min(1.0, abs(defect_rows.height - clean_rows.height) / clean_rows.height)
    total = alpha + BETA + gamma
    silence = alpha / total if total > 0 else 0.0
    return {
        "tau_pred": tau_pred,
        "alpha": alpha,
        "beta": BETA,
        "gamma": gamma,
        "silence_index": min(1.0, max(0.0, silence)),
        "matched_rows": joined.height,
    }


def _predict(model: Any, frame: pl.DataFrame) -> pl.DataFrame:
    features, _ = to_xy(frame)
    yhat = np.asarray(model.predict(features), dtype=np.float64)
    return frame.select([PROVENANCE_COLUMN, OCCURRENCE_COLUMN, TARGET]).with_columns(
        pl.Series("yhat", yhat)
    )


def _fit(
    prepared: PreparedTlc, *, seed: int, num_boost_round: int
) -> tuple[Any, dict[str, pl.DataFrame], dict[str, dict[str, float]]]:
    X_train, y_train = to_xy(prepared.splits["train"])
    X_val, y_val = to_xy(prepared.splits["validation"])
    model = train_lightgbm(
        X_train,
        y_train,
        X_val,
        y_val,
        seed=seed,
        num_boost_round=num_boost_round,
    )
    predictions = {name: _predict(model, frame) for name, frame in prepared.splits.items()}
    metrics = {
        name: regression_metrics(frame[TARGET].to_numpy(), frame["yhat"].to_numpy())
        for name, frame in predictions.items()
    }
    return model, predictions, metrics


def _inject(prepared: PreparedTlc, *, severity: float, seed: int) -> PreparedTlc:
    return PreparedTlc(
        splits={
            name: duplicate_ingestion(frame, severity=severity, seed=seed)
            for name, frame in prepared.splits.items()
        },
        raw_rows=prepared.raw_rows,
        clean_rows=prepared.clean_rows,
        files=prepared.files,
    )


def _flat_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{split}_{name}": value
        for split, values in metrics.items()
        for name, value in values.items()
    }


def _metric_difference(
    left: dict[str, dict[str, float]], right: dict[str, dict[str, float]]
) -> float:
    return max(
        abs(value - right[split][name])
        for split, values in left.items()
        for name, value in values.items()
    )


def _prediction_difference(left: pl.DataFrame, right: pl.DataFrame) -> float:
    left_first = left.unique(subset=[PROVENANCE_COLUMN], keep="first")
    right_first = right.unique(subset=[PROVENANCE_COLUMN], keep="first")
    joined = left_first.select([PROVENANCE_COLUMN, "yhat"]).join(
        right_first.select([PROVENANCE_COLUMN, "yhat"]),
        on=PROVENANCE_COLUMN,
        how="inner",
        suffix="_right",
    )
    if joined.height != left_first.height:
        return math.inf
    value = (joined["yhat"] - joined["yhat_right"]).abs().max()
    return math.inf if value is None else float(cast(float, value))


def run_smoke(
    raw_dir: Path,
    artifacts_dir: Path,
    *,
    seed: int = 42,
    num_boost_round: int = 50,
    severity: float = 0.10,
) -> dict[str, Any]:
    """Run clean twice and one D5 condition, then write records and artifacts."""
    prepared = prepare_tlc(raw_dir, seed=seed)
    _, clean_predictions, clean_metrics = _fit(prepared, seed=seed, num_boost_round=num_boost_round)
    _, rerun_predictions, rerun_metrics = _fit(prepared, seed=seed, num_boost_round=num_boost_round)
    defect_prepared = _inject(prepared, severity=severity, seed=seed)
    _, defect_predictions, defect_metrics = _fit(
        defect_prepared, seed=seed, num_boost_round=num_boost_round
    )

    clean_pair = annotate_pair(clean_predictions, rerun_predictions)
    defect_pair = annotate_pair(clean_predictions, defect_predictions)
    metric_delta = _metric_difference(clean_metrics, rerun_metrics)
    prediction_delta = max(
        _prediction_difference(clean_predictions[name], rerun_predictions[name])
        for name in clean_predictions
    )
    checks = {
        "clean_rerun_metrics_identical": metric_delta <= 1e-9,
        "clean_rerun_predictions_identical": prediction_delta <= 1e-9,
        "clean_clean_zero": (
            clean_pair["alpha"] == 0.0 and clean_pair["beta"] == 0.0 and clean_pair["gamma"] == 0.0
        ),
        "defect_gamma_matches_severity": abs(float(defect_pair["gamma"]) - severity) <= 0.02,
    }

    thresholds_hash = config_hash(
        {"tau_multiplier": TAU_MULTIPLIER, "beta": "p0-zero", "version": 1}
    )
    store = RunStore(artifacts_dir / "runs")
    clean_record = RunRecord(
        run_id=f"smoke-clean-{seed}",
        dataset="tlc",
        task="eta-regression",
        model="lightgbm",
        seed=seed,
        config_hash=config_hash(
            {
                "experiment": "smoke",
                "treatment": "clean",
                "seed": seed,
                "rounds": num_boost_round,
            }
        ),
        status="completed",
        metrics=_flat_metrics(clean_metrics),
        alpha=float(clean_pair["alpha"]),
        beta=float(clean_pair["beta"]),
        gamma=float(clean_pair["gamma"]),
        silence_index=float(clean_pair["silence_index"]),
        matched_rows=int(clean_pair["matched_rows"]),
        tau_pred=float(clean_pair["tau_pred"]),
        thresholds_hash=thresholds_hash,
    )
    defect_record = RunRecord(
        run_id=f"smoke-d5-{seed}",
        dataset="tlc",
        task="eta-regression",
        model="lightgbm",
        seed=seed,
        config_hash=config_hash(
            {
                "experiment": "smoke",
                "treatment": "D5",
                "severity": severity,
                "seed": seed,
                "rounds": num_boost_round,
            }
        ),
        status="completed",
        metrics=_flat_metrics(defect_metrics),
        alpha=float(defect_pair["alpha"]),
        beta=float(defect_pair["beta"]),
        gamma=float(defect_pair["gamma"]),
        silence_index=float(defect_pair["silence_index"]),
        matched_rows=int(defect_pair["matched_rows"]),
        tau_pred=float(defect_pair["tau_pred"]),
        thresholds_hash=thresholds_hash,
    )
    store.save(clean_record, force=True)
    store.save(defect_record, force=True)

    for label, predictions in (
        ("clean", clean_predictions),
        ("defect", defect_predictions),
    ):
        for split, frame in predictions.items():
            path = artifacts_dir / "predictions" / label / f"{split}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(path)

    summary: dict[str, Any] = {
        "seed": seed,
        "severity": severity,
        "rounds": num_boost_round,
        "rows": {name: frame.height for name, frame in prepared.splits.items()},
        "defect_rows": {name: frame.height for name, frame in defect_prepared.splits.items()},
        "metrics": {
            "clean": clean_metrics,
            "rerun": rerun_metrics,
            "defect": defect_metrics,
        },
        "annotation": {
            "clean_clean": clean_pair,
            "clean_defect": defect_pair,
        },
        "checks": checks,
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError("smoke checks failed: " + ", ".join(failed))
    return summary
