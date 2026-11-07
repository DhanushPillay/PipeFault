from __future__ import annotations

import math

import pytest

from pipefault.records import RunRecord, canonical_json, config_hash, with_annotation


def make_record(**overrides: object) -> RunRecord:
    data: dict[str, object] = {
        "run_id": "run-abc",
        "dataset": "tlc",
        "task": "regression",
        "model": "lightgbm",
        "seed": 42,
        "config_hash": "a" * 64,
        "status": "completed",
    }
    data.update(overrides)
    return RunRecord(**data)  # type: ignore[arg-type]


def test_config_hash_is_key_order_invariant() -> None:
    first = {"dataset": "tlc", "seed": 42, "defects": ["D1", "D5"]}
    second = {"defects": ["D1", "D5"], "seed": 42, "dataset": "tlc"}

    assert canonical_json(first) == '{"dataset":"tlc","defects":["D1","D5"],"seed":42}'
    assert config_hash(first) == config_hash(second)
    assert config_hash(first) != config_hash({**first, "seed": 43})


def test_config_hash_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"metric": math.nan})


def test_run_record_round_trip() -> None:
    record = make_record(
        reason=None,
        metrics={"rmse": 7.2, "mae": 4.6},
        alpha=0.12,
        beta=0.3,
        gamma=0.05,
        silence_index=0.26,
        matched_rows=1000,
        tau_pred=0.7,
        thresholds_hash="b" * 64,
        alpha_definition_version="1",
        oracle=True,
        created_at="2026-11-07T00:00:00Z",
    )

    assert RunRecord.from_json(record.to_json()) == record
    assert RunRecord.from_dict(record.to_dict()) == record
    assert record.annotation_complete


def test_with_annotation_computes_silence_index() -> None:
    record = make_record(metrics={"test_rmse": 7.5})

    annotated = with_annotation(
        record,
        alpha=0.2,
        beta=0.1,
        gamma=0.1,
        matched_rows=1000,
        tau_pred=0.7,
        thresholds_hash="b" * 64,
    )

    assert annotated.annotation_complete
    assert annotated.silence_index == pytest.approx(0.5)
    assert annotated.oracle is True
    assert annotated.alpha_definition_version == "1"
    assert RunRecord.from_json(annotated.to_json()) == annotated


def test_with_annotation_rejects_bad_pairs_and_zero_signal() -> None:
    record = make_record()
    zero = with_annotation(
        record,
        alpha=0.0,
        beta=0.0,
        gamma=0.0,
        matched_rows=10,
        tau_pred=0.5,
        thresholds_hash="b" * 64,
    )
    assert zero.silence_index == 0.0

    with pytest.raises(ValueError, match="matched rows"):
        with_annotation(
            record,
            alpha=0.1,
            beta=0.0,
            gamma=0.0,
            matched_rows=0,
            tau_pred=0.5,
            thresholds_hash="b" * 64,
        )
    with pytest.raises(ValueError, match="completed"):
        with_annotation(
            make_record(status="failed", reason="crashed"),
            alpha=0.1,
            beta=0.0,
            gamma=0.0,
            matched_rows=10,
            tau_pred=0.5,
            thresholds_hash="b" * 64,
        )


def test_annotation_incomplete_without_all_fields() -> None:
    record = make_record(alpha=0.1, beta=0.2)

    assert not record.annotation_complete


def test_failed_record_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        make_record(status="failed")

    assert make_record(status="failed", reason="engine crashed").status == "failed"


def test_invalid_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="alpha"):
        make_record(alpha=1.5)
    with pytest.raises(ValueError, match="matched_rows"):
        make_record(matched_rows=-1)
    with pytest.raises(ValueError, match="tau_pred"):
        make_record(tau_pred=0.0)
    with pytest.raises(ValueError, match="status"):
        make_record(status="running")
    with pytest.raises(ValueError, match="run_id"):
        make_record(run_id=" ")
    with pytest.raises(ValueError, match="finite"):
        make_record(metrics={"rmse": math.inf})
    with pytest.raises(ValueError, match="alpha_definition_version"):
        make_record(alpha_definition_version=" ")
    with pytest.raises(ValueError, match="oracle"):
        make_record(oracle="yes")  # type: ignore[arg-type]


def test_unknown_and_missing_fields_are_rejected() -> None:
    record = make_record()

    with pytest.raises(ValueError, match="unknown"):
        RunRecord.from_dict({**record.to_dict(), "extra": 1})

    broken = record.to_dict()
    del broken["config_hash"]
    with pytest.raises(ValueError, match="missing"):
        RunRecord.from_dict(broken)


def test_metadata_round_trip_and_serializable_check() -> None:
    record = make_record(metadata={"defect": "D5", "realized_severity": 0.1})

    assert RunRecord.from_json(record.to_json()) == record
    assert RunRecord.from_dict(record.to_dict()).metadata == record.metadata

    with pytest.raises(ValueError, match="JSON-serializable"):
        make_record(metadata={"bad": object()})
