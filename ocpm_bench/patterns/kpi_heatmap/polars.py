"""K1 (heatmap) via Polars."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel


def run(model: PolarsModel, _inputs) -> list[tuple[str, str, int]]:
    agg = (
        model.relations.lazy()
        .group_by(["ocel:activity", "ocel:type"])
        .agg(pl.len().alias("count"))
        .collect()
    )
    return [(str(a), str(t), int(c)) for a, t, c in agg.iter_rows()]


registry.register_impl("kpi_heatmap", "polars", sys.modules[__name__])
