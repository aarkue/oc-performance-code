"""Result row and JSONL writer. One row per (cell, query instance)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ResultRow:
    model: str
    pattern: str
    instance_id: str
    dataset: str
    repetitions: int
    warm_ms: list[float]
    cold_ms: float
    model_bytes: int | None
    rss_bytes_after_setup: int | None
    correct: bool
    oracle_model: str
    lib_versions: dict[str, str]
    matrix_pass: int
    timestamp: str = field(default_factory=_now_utc)

    @classmethod
    def from_observations(
        cls,
        *,
        model: str,
        pattern: str,
        instance_id: str,
        dataset: str,
        warm_ms: list[float],
        cold_ms: float,
        model_bytes: int | None,
        rss_bytes_after_setup: int | None,
        correct: bool,
        lib_versions: dict[str, str],
        matrix_pass: int,
        oracle_model: str = "linked_ocel",
    ) -> ResultRow:
        return cls(
            model=model, pattern=pattern,
            instance_id=instance_id, dataset=dataset,
            repetitions=len(warm_ms), warm_ms=warm_ms, cold_ms=cold_ms,
            model_bytes=model_bytes, rss_bytes_after_setup=rss_bytes_after_setup,
            correct=correct,
            oracle_model=oracle_model, lib_versions=lib_versions,
            matrix_pass=matrix_pass,
        )


def write_jsonl(path: Path, rows: list[ResultRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in rows:
            f.write(json.dumps(asdict(r)) + "\n")
