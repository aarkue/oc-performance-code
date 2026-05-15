"""Variants via polars: list-aggregate then group-count via a delimiter join."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.base import PerTypeInputs
from ocpm_bench.patterns.variants import DELIM


def run(model: PolarsModel, inputs: PerTypeInputs) -> list[tuple]:
    agg = (
        model.relations
        .filter(pl.col("ocel:type") == inputs.object_type)
        .sort(["ocel:oid", "ocel:timestamp", "ocel:eid"])
        .group_by("ocel:oid", maintain_order=False)
        .agg(pl.col("ocel:activity"))
        .with_columns(pl.col("ocel:activity").list.join(DELIM).alias("trace_str"))
        .group_by("trace_str")
        .agg(pl.len().alias("count"))
    )
    return [(tuple(trace_str.split(DELIM)), int(cnt)) for trace_str, cnt in agg.iter_rows()]


registry.register_impl("variants", "polars", sys.modules[__name__])
