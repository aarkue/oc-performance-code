"""DFG via polars: window-shift on the relations frame."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.base import PerTypeInputs


def run(model: PolarsModel, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    agg = (
        model.relations
        .filter(pl.col("ocel:type") == inputs.object_type)
        .sort(["ocel:oid", "ocel:timestamp", "ocel:eid"])
        .with_columns(
            pl.col("ocel:activity").shift(-1).over("ocel:oid").alias("next")
        )
        .drop_nulls("next")
        .group_by(["ocel:activity", "next"])
        .agg(pl.len().alias("count"))
    )
    return [(src, tgt, int(cnt)) for src, tgt, cnt in agg.iter_rows()]


registry.register_impl("dfg", "polars", sys.modules[__name__])
