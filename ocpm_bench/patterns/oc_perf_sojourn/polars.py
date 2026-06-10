"""Sojourn via Polars: per-event time since the latest predecessor."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns._perf_topk import perf_top_k


def run(model: PolarsModel, _inputs) -> list[tuple[str, int]]:
    lf = (
        model.relations.lazy()
        .select([
            pl.col("ocel:eid"),
            pl.col("ocel:oid"),
            pl.col("ocel:timestamp").dt.timestamp("us").alias("t_us"),
        ])
        .sort(["ocel:oid", "t_us", "ocel:eid"])
        .with_columns(pred_us=pl.col("t_us").shift(1).over("ocel:oid"))
        .filter(pl.col("pred_us").is_not_null())
        .group_by("ocel:eid")
        .agg((pl.col("t_us").max() - pl.col("pred_us").max()).alias("sojourn_us"))
    )
    k = perf_top_k()
    if k is not None:
        lf = lf.sort(["sojourn_us", "ocel:eid"], descending=[True, False]).head(k)
    out = lf.collect()
    return [(str(e), int(s)) for e, s in out.iter_rows()]


registry.register_impl("oc_perf_sojourn", "polars", sys.modules[__name__])
