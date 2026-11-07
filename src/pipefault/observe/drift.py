"""PSI and KS drift statistics with frozen clean-validation thresholds."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import polars as pl

from pipefault.records import config_hash

FAMILIES = ("psi", "ks")
_EPSILON = 1e-6
_THRESHOLD_FLOOR = 1e-12


def _as_array(value: Any) -> np.ndarray:
    if isinstance(value, pl.Series):
        data = value.drop_nulls().to_numpy()
    else:
        data = np.asarray(value, dtype=np.float64).ravel()
        data = data[np.isfinite(data)]
    return np.asarray(data, dtype=np.float64)


def psi(reference: Any, current: Any, *, bins: int = 10) -> float:
    """Population stability index over reference quantile bins."""
    if bins < 2:
        raise ValueError("bins must be at least 2")
    ref = _as_array(reference)
    cur = _as_array(current)
    if ref.size == 0 or cur.size == 0:
        raise ValueError("psi needs non-empty reference and current samples")

    edges = np.unique(np.quantile(ref, np.linspace(0.0, 1.0, bins + 1)))
    if edges.size < 2:
        return 0.0 if np.all(cur == edges[0]) else math.inf
    edges[0] = -math.inf
    edges[-1] = math.inf

    ref_share = np.histogram(ref, bins=edges)[0] / ref.size
    cur_share = np.histogram(cur, bins=edges)[0] / cur.size
    ref_share = np.where(ref_share == 0.0, _EPSILON, ref_share)
    cur_share = np.where(cur_share == 0.0, _EPSILON, cur_share)
    return float(np.sum((ref_share - cur_share) * np.log(ref_share / cur_share)))


def ks_statistic(reference: Any, current: Any) -> float:
    """Two-sample Kolmogorov-Smirnov statistic without scipy."""
    ref = np.sort(_as_array(reference))
    cur = np.sort(_as_array(current))
    if ref.size == 0 or cur.size == 0:
        raise ValueError("ks needs non-empty reference and current samples")

    grid = np.concatenate([ref, cur])
    ref_cdf = np.searchsorted(ref, grid, side="right") / ref.size
    cur_cdf = np.searchsorted(cur, grid, side="right") / cur.size
    return float(np.max(np.abs(ref_cdf - cur_cdf)))


def feature_statistics(
    reference: pl.DataFrame,
    frame: pl.DataFrame,
    *,
    features: Sequence[str],
    bins: int = 10,
) -> dict[str, dict[str, float]]:
    """PSI and KS for every monitored feature."""
    missing = [
        name for name in features if name not in reference.columns or name not in frame.columns
    ]
    if missing:
        raise ValueError(f"missing monitored features: {', '.join(missing)}")
    return {
        "psi": {name: psi(reference[name], frame[name], bins=bins) for name in features},
        "ks": {name: ks_statistic(reference[name], frame[name]) for name in features},
    }


def calibrate_thresholds(
    reference: pl.DataFrame,
    batches: Sequence[pl.DataFrame],
    *,
    features: Sequence[str],
    false_alarm: float = 0.01,
    bins: int = 10,
) -> dict[str, dict[str, float]]:
    """Freeze one threshold per family and feature at the clean batch quantile."""
    if not batches:
        raise ValueError("calibration needs at least one clean batch")
    if not 0.0 < false_alarm < 1.0:
        raise ValueError("false_alarm must be in (0, 1)")

    collected: dict[str, dict[str, list[float]]] = {
        family: {name: [] for name in features} for family in FAMILIES
    }
    for batch in batches:
        statistics = feature_statistics(reference, batch, features=features, bins=bins)
        for family in FAMILIES:
            for name in features:
                collected[family][name].append(statistics[family][name])

    return {
        family: {
            name: max(
                _THRESHOLD_FLOOR,
                float(np.quantile(collected[family][name], 1.0 - false_alarm)),
            )
            for name in features
        }
        for family in FAMILIES
    }


def beta_for_frame(
    reference: pl.DataFrame,
    frame: pl.DataFrame,
    *,
    thresholds: dict[str, dict[str, float]],
    features: Sequence[str],
    bins: int = 10,
) -> tuple[float, dict[str, dict[str, float]]]:
    """Normalized drift severity: max over families and features of stat/threshold."""
    statistics = feature_statistics(reference, frame, features=features, bins=bins)
    normalized: dict[str, dict[str, float]] = {}
    for family in FAMILIES:
        normalized[family] = {}
        for name in features:
            threshold = max(_THRESHOLD_FLOOR, thresholds[family][name])
            value = statistics[family][name]
            if not math.isfinite(value):
                normalized[family][name] = 1.0
            else:
                normalized[family][name] = min(1.0, value / threshold)
    beta = max(value for family in FAMILIES for value in normalized[family].values())
    return beta, normalized


def thresholds_hash(thresholds: dict[str, dict[str, float]]) -> str:
    """Stable hash of a frozen threshold table."""
    return config_hash(thresholds)
