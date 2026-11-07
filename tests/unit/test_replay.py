from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from pipefault.data.provenance import add_provenance
from pipefault.simulate.replay import (
    INGEST_TIME,
    LATENESS_SECONDS,
    WITHIN_LATENESS,
    ReplaySpec,
    apply_watermark,
    replay,
)


def _events(rows: int = 1000) -> pl.DataFrame:
    start = datetime(2024, 1, 1, 0, 0)
    frame = pl.DataFrame(
        {"tpep_pickup_datetime": [start + timedelta(minutes=i) for i in range(rows)]}
    )
    return add_provenance(frame, dataset="tlc", file="a.parquet")


def _spec() -> ReplaySpec:
    return ReplaySpec(
        time_column="tpep_pickup_datetime",
        allowed_lateness_seconds=3600,
        on_time_share=0.80,
        late_share=0.15,
        seed=42,
    )


def test_replay_is_deterministic() -> None:
    frame = _events()

    first = replay(frame, _spec())
    second = replay(frame, _spec())

    assert first.equals(second)


def test_replay_assigns_exact_delay_groups() -> None:
    frame = _events(1000)

    result = replay(frame, _spec())

    on_time = result.filter(pl.col(LATENESS_SECONDS) == 0)
    late = result.filter((pl.col(LATENESS_SECONDS) > 0) & (pl.col(LATENESS_SECONDS) <= 3600))
    too_late = result.filter(pl.col(LATENESS_SECONDS) > 3600)

    assert on_time.height == 800
    assert late.height == 150
    assert too_late.height == 50
    assert late[LATENESS_SECONDS].min() >= 1
    assert late[LATENESS_SECONDS].max() <= 3600
    assert too_late[LATENESS_SECONDS].min() > 3600
    assert too_late[LATENESS_SECONDS].max() <= 7200


def test_replay_preserves_row_order_and_ingest_math() -> None:
    frame = _events(100)

    result = replay(frame, _spec())

    assert result["pf_row_id"].to_list() == frame["pf_row_id"].to_list()
    delta = (result[INGEST_TIME] - result["tpep_pickup_datetime"]).dt.total_seconds()
    assert delta.to_list() == result[LATENESS_SECONDS].to_list()
    assert result[WITHIN_LATENESS].sum() == 95


def test_watermark_drops_exactly_the_too_late_events() -> None:
    frame = _events(1000)
    replayed = replay(frame, _spec())

    kept, dropped = apply_watermark(replayed, allowed_lateness_seconds=3600)

    assert dropped == 50
    assert kept.height == 950
    assert kept[LATENESS_SECONDS].max() <= 3600


def test_invalid_spec_and_missing_column_are_rejected() -> None:
    with pytest.raises(ValueError, match="at most 1"):
        ReplaySpec(on_time_share=0.9, late_share=0.2)

    with pytest.raises(ValueError, match="missing event time"):
        replay(pl.DataFrame({"value": [1]}), _spec())
