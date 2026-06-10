"""Sync via Polars: per-event span + delaying object."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns._perf_topk import perf_top_k


def run(model: PolarsModel, _inputs) -> list[tuple[str, int, str]]:
    base = (
        model.relations.lazy()
        .select([
            pl.col("ocel:eid"),
            pl.col("ocel:oid"),
            pl.col("ocel:timestamp").dt.timestamp("us").alias("t_us"),
        ])
        .sort(["ocel:oid", "t_us", "ocel:eid"])
        .with_columns(pred_us=pl.col("t_us").shift(1).over("ocel:oid"))
        .filter(pl.col("pred_us").is_not_null())
    )
    span = base.group_by("ocel:eid").agg(
        (pl.col("pred_us").max() - pl.col("pred_us").min()).alias("sync_us")
    )
    delaying = (
        base.sort(["ocel:eid", "pred_us", "ocel:oid"], descending=[False, True, False])
        .group_by("ocel:eid", maintain_order=True)
        .agg(pl.col("ocel:oid").first().alias("delaying_object"))
    )
    joined = span.join(delaying, on="ocel:eid")
    k = perf_top_k()
    if k is not None:
        joined = joined.sort(["sync_us", "ocel:eid"], descending=[True, False]).head(k)
    out = joined.collect()
    return [(str(e), int(s), str(o)) for e, s, o in out.iter_rows()]


registry.register_impl("oc_perf_sync", "polars", sys.modules[__name__])
