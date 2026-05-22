"""W2 via Polars: df-edge based via per-object shift, argmax via sort + first."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel


def run(model: PolarsModel, _inputs) -> list[tuple[str, str, int]]:
    rel = (
        model.relations.lazy()
        .select(
            ["ocel:eid", "ocel:activity", "ocel:timestamp", "ocel:oid", "ocel:type"]
        )
        .sort(["ocel:oid", "ocel:timestamp", "ocel:eid"])
        .with_columns(
            pred_t=pl.col("ocel:timestamp").shift(1).over("ocel:oid"),
            pred_activity=pl.col("ocel:activity").shift(1).over("ocel:oid"),
        )
        .filter(pl.col("pred_t").is_not_null())
    )

    picked = (
        rel.sort(
            ["ocel:eid", "pred_t", "ocel:oid"],
            descending=[False, True, False],
        )
        .group_by("ocel:eid", maintain_order=True)
        .agg(
            pl.col("pred_activity").first(),
            pl.col("ocel:type").first(),
        )
    )

    out = (
        picked.group_by(["pred_activity", "ocel:type"])
        .agg(pl.len().alias("count"))
        .collect()
    )
    return [(str(r[0]), str(r[1]), int(r[2])) for r in out.iter_rows()]


registry.register_impl("oc_perf_delaying", "polars", sys.modules[__name__])
