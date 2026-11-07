"""Injector protocol, shared result type, and deterministic helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import polars as pl

from pipefault.data.provenance import PROVENANCE_COLUMN

_PF_SELECT_HASH = "_pf_select_hash"


@dataclass(frozen=True)
class InjectionResult:
    """Outcome of one injection.

    ``affected_units`` counts the entities the defect targets (keys, events,
    partitions). ``affected_rows`` counts output rows the treatment touches.
    ``realized_severity`` is recomputed from the frame, never copied from the
    request.
    """

    name: str
    severity: float
    realized_severity: float
    affected_units: int
    affected_rows: int
    data: pl.DataFrame
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        validate_severity(self.severity)
        validate_severity(self.realized_severity)
        if self.affected_units < 0 or self.affected_rows < 0:
            raise ValueError("affected counts must be non-negative")


class Injector(Protocol):
    """One defect operator. Implementations are stateless and seed-driven."""

    name: str

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult: ...


def validate_severity(severity: float) -> float:
    if not 0.0 <= severity <= 1.0:
        raise ValueError("severity must be in [0, 1]")
    return severity


def derive_seed(master_seed: int, *, defect: str, severity: float, purpose: str = "") -> int:
    """Derive an independent seed per condition so injectors cannot share RNG."""
    payload = f"{master_seed}|{defect}|{severity:.6f}|{purpose}"
    return int.from_bytes(hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest(), "big")


def select_top(
    frame: pl.DataFrame,
    *,
    count: int,
    seed: int,
    keys: Sequence[str] | None = None,
) -> pl.DataFrame:
    """Return the ``count`` rows with the smallest hash of ``keys``.

    Deterministic and independent of input order. ``keys`` defaults to the
    provenance id, which is unique per source row.
    """
    if count < 0:
        raise ValueError("count must be non-negative")
    if count == 0:
        return frame.head(0)
    if count >= frame.height:
        return frame

    key_columns = list(keys) if keys else [PROVENANCE_COLUMN]
    missing = [column for column in key_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing selection keys: {', '.join(missing)}")

    return (
        frame.with_columns(
            pl.struct([pl.col(column) for column in key_columns])
            .hash(seed=seed)
            .alias(_PF_SELECT_HASH)
        )
        .sort(_PF_SELECT_HASH)
        .head(count)
        .drop(_PF_SELECT_HASH)
    )
