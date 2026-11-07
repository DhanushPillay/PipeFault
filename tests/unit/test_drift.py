from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from pipefault.observe.drift import (
    beta_for_frame,
    calibrate_thresholds,
    feature_statistics,
    ks_statistic,
    psi,
    thresholds_hash,
)


def _batch(rows: int, *, shift: float = 0.0, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    return pl.DataFrame(
        {
            "batch_id": ["2024-01-01"] * rows,
            "a": rng.normal(0.0, 1.0, size=rows) + shift,
            "b": rng.normal(0.0, 2.0, size=rows) + shift,
        }
    )


def test_psi_is_zero_for_identical_and_grows_with_shift() -> None:
    base = _batch(500, seed=1)

    assert psi(base["a"], base["a"]) == pytest.approx(0.0, abs=1e-9)
    small = psi(base["a"], _batch(500, shift=0.5, seed=2)["a"])
    large = psi(base["a"], _batch(500, shift=3.0, seed=2)["a"])

    assert 0.0 < small < large
    assert large > 0.2


def test_ks_matches_hand_computed_values() -> None:
    assert ks_statistic([0.0, 1.0], [0.0, 1.0]) == 0.0
    assert ks_statistic([0.0, 1.0], [10.0, 11.0]) == 1.0
    assert ks_statistic([0.0, 1.0], [0.5, 1.5]) == pytest.approx(0.5)


def test_feature_statistics_covers_every_feature_and_family() -> None:
    reference = _batch(200, seed=3)
    current = _batch(200, shift=0.5, seed=4)

    statistics = feature_statistics(reference, current, features=["a", "b"])

    assert set(statistics) == {"psi", "ks"}
    assert set(statistics["psi"]) == {"a", "b"}
    assert set(statistics["ks"]) == {"a", "b"}
    assert all(value >= 0.0 for family in statistics.values() for value in family.values())


def test_constant_reference_is_handled() -> None:
    reference = pl.DataFrame({"a": [5.0, 5.0, 5.0]})

    assert psi(reference["a"], reference["a"]) == 0.0
    assert psi(reference["a"], [6.0, 6.0]) == math.inf


def test_calibration_uses_the_false_alarm_quantile() -> None:
    reference = _batch(300, seed=5)
    batches = [_batch(300, seed=seed) for seed in range(20)]

    thresholds = calibrate_thresholds(reference, batches, features=["a", "b"])
    statistics = [
        feature_statistics(reference, batch, features=["a"])["psi"]["a"] for batch in batches
    ]

    assert thresholds["psi"]["a"] == pytest.approx(float(np.quantile(statistics, 0.99)))
    assert thresholds["ks"]["b"] > 0.0


def test_beta_is_the_max_normalized_statistic() -> None:
    reference = _batch(300, seed=6)
    current = _batch(300, shift=2.0, seed=7)
    thresholds = {"psi": {"a": 0.05, "b": 0.05}, "ks": {"a": 0.2, "b": 0.2}}

    beta, series = beta_for_frame(reference, current, thresholds=thresholds, features=["a", "b"])

    statistics = feature_statistics(reference, current, features=["a", "b"])
    expected = max(
        min(1.0, statistics[family][name] / thresholds[family][name])
        for family in ("psi", "ks")
        for name in ("a", "b")
    )
    assert beta == pytest.approx(expected)
    assert 0.0 <= beta <= 1.0
    assert all(0.0 <= value <= 1.0 for family in series.values() for value in family.values())


def test_clean_pair_gives_zero_beta() -> None:
    reference = _batch(200, seed=8)
    thresholds = {"psi": {"a": 0.1, "b": 0.1}, "ks": {"a": 0.2, "b": 0.2}}

    beta, series = beta_for_frame(reference, reference, thresholds=thresholds, features=["a", "b"])

    assert beta == 0.0
    assert all(value == 0.0 for family in series.values() for value in family.values())


def test_threshold_hash_is_stable() -> None:
    thresholds = {"psi": {"a": 0.1}, "ks": {"a": 0.2}}

    assert thresholds_hash(thresholds) == thresholds_hash({"ks": {"a": 0.2}, "psi": {"a": 0.1}})


def test_invalid_drift_inputs_are_rejected() -> None:
    frame = _batch(10, seed=9)

    with pytest.raises(ValueError, match="non-empty"):
        psi([], [1.0])
    with pytest.raises(ValueError, match="bins"):
        psi([1.0, 2.0], [1.0], bins=1)
    with pytest.raises(ValueError, match="missing monitored features"):
        feature_statistics(frame, frame, features=["nope"])
    with pytest.raises(ValueError, match="at least one clean batch"):
        calibrate_thresholds(frame, [], features=["a"])
    with pytest.raises(ValueError, match="false_alarm"):
        calibrate_thresholds(frame, [frame], features=["a"], false_alarm=1.0)
