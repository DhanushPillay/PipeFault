"""Run records with canonical config hashing."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, replace
from typing import Any

STATUSES = frozenset({"completed", "failed", "skipped"})
_EPSILON = 1e-12


def canonical_json(value: Any) -> str:
    """Serialize a value so equal configs always produce equal bytes."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def config_hash(config: Any) -> str:
    """Return the SHA-256 of the canonical JSON encoding."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RunRecord:
    """One condition outcome. Annotation fields are filled after pairing."""

    run_id: str
    dataset: str
    task: str
    model: str
    seed: int
    config_hash: str
    status: str
    reason: str | None = None
    metrics: dict[str, float] | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    silence_index: float | None = None
    matched_rows: int | None = None
    tau_pred: float | None = None
    thresholds_hash: str | None = None
    alpha_definition_version: str | None = None
    oracle: bool | None = None
    created_at: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "dataset", "task", "model", "config_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        if self.status == "failed" and not (self.reason and self.reason.strip()):
            raise ValueError("failed runs require a non-empty reason")
        for name in ("alpha", "beta", "gamma", "silence_index"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.matched_rows is not None and self.matched_rows < 0:
            raise ValueError("matched_rows must be non-negative")
        if self.tau_pred is not None and self.tau_pred <= 0:
            raise ValueError("tau_pred must be positive")
        if self.thresholds_hash is not None and not self.thresholds_hash.strip():
            raise ValueError("thresholds_hash must be non-empty when present")
        if self.alpha_definition_version is not None and not self.alpha_definition_version.strip():
            raise ValueError("alpha_definition_version must be non-empty when present")
        if self.oracle is not None and not isinstance(self.oracle, bool):
            raise ValueError("oracle must be a boolean when present")
        if self.metrics is not None:
            for key, value in self.metrics.items():
                if not key:
                    raise ValueError("metric names must be non-empty")
                if not math.isfinite(value):
                    raise ValueError(f"metric {key!r} is not finite")
        if self.metadata is not None:
            if not isinstance(self.metadata, dict):
                raise ValueError("metadata must be a mapping")
            for key in self.metadata:
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("metadata keys must be non-empty strings")
            try:
                canonical_json(self.metadata)
            except TypeError as exc:
                raise ValueError("metadata must be JSON-serializable") from exc

    @property
    def annotation_complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.alpha,
                self.beta,
                self.gamma,
                self.silence_index,
                self.matched_rows,
                self.tau_pred,
                self.thresholds_hash,
                self.alpha_definition_version,
                self.oracle,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown run record fields: {', '.join(unknown)}")
        required = {"run_id", "dataset", "task", "model", "seed", "config_hash", "status"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"missing run record fields: {', '.join(missing)}")
        return cls(
            run_id=data["run_id"],
            dataset=data["dataset"],
            task=data["task"],
            model=data["model"],
            seed=data["seed"],
            config_hash=data["config_hash"],
            status=data["status"],
            reason=data.get("reason"),
            metrics=data.get("metrics"),
            alpha=data.get("alpha"),
            beta=data.get("beta"),
            gamma=data.get("gamma"),
            silence_index=data.get("silence_index"),
            matched_rows=data.get("matched_rows"),
            tau_pred=data.get("tau_pred"),
            thresholds_hash=data.get("thresholds_hash"),
            alpha_definition_version=data.get("alpha_definition_version"),
            oracle=data.get("oracle"),
            created_at=data.get("created_at"),
            metadata=data.get("metadata"),
        )

    @classmethod
    def from_json(cls, text: str) -> RunRecord:
        return cls.from_dict(json.loads(text))


def with_annotation(
    record: RunRecord,
    *,
    alpha: float,
    beta: float,
    gamma: float,
    matched_rows: int,
    tau_pred: float,
    thresholds_hash: str,
    alpha_definition_version: str = "1",
    oracle: bool = True,
) -> RunRecord:
    """Return a completed record with annotation fields and the silence index."""
    if record.status != "completed":
        raise ValueError("only completed records can be annotated")
    if matched_rows <= 0:
        raise ValueError("annotation requires matched rows; pairing is bad")
    total = alpha + beta + gamma
    silence_index = 0.0 if total <= 0 else min(1.0, alpha / (total + _EPSILON))
    return replace(
        record,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        silence_index=silence_index,
        matched_rows=matched_rows,
        tau_pred=tau_pred,
        thresholds_hash=thresholds_hash,
        alpha_definition_version=alpha_definition_version,
        oracle=oracle,
    )
