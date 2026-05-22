"""W1 via Polars: df-edge based via per-object shift after sort."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel


def run(model: PolarsModel, _inputs) -> list[tuple[str, int, int]]:
    rel = (
        model.relations.lazy()
        .select(["ocel:eid", "ocel:activity", "ocel:timestamp", "ocel:oid"])
        .sort(["ocel:oid", "ocel:timestamp", "ocel:eid"])
        .with_columns(
            pred_t=pl.col("ocel:timestamp").shift(1).over("ocel:oid"),
        )
        .filter(pl.col("pred_t").is_not_null())
    )

    per_event = rel.group_by(["ocel:eid", "ocel:activity"]).agg(
        t_min=pl.col("pred_t").min(),
        t_max=pl.col("pred_t").max(),
    ).with_columns(
        span_s=((pl.col("t_max") - pl.col("t_min")).dt.total_seconds()).cast(pl.Int64)
    )

    out = per_event.group_by("ocel:activity").agg(
        total=pl.col("span_s").sum(),
        count=pl.col("span_s").count(),
    ).collect()

    return [(str(row[0]), int(row[1]), int(row[2])) for row in out.iter_rows()]


registry.register_impl("oc_perf_sync", "polars", sys.modules[__name__])
