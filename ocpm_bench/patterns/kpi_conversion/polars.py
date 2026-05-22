"""K2 (conversion rate) via Polars.

Source -> O2O -> Target -> E2O <- Event with activity. Fraction of distinct
sources reached.
"""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs


def run(model: PolarsModel, inputs: KPIConversionInputs) -> float:
    objs = model.objects.lazy()
    rel = model.relations.lazy()
    o2o = model.frames["o2o"].lazy()

    sources = objs.filter(pl.col("ocel:type") == inputs.source_type).select("ocel:oid")
    total = sources.select(pl.len()).collect().item()
    if total == 0:
        return 0.0

    reached_targets = (
        rel.filter(
            (pl.col("ocel:activity") == inputs.activity)
            & (pl.col("ocel:type") == inputs.target_type)
        )
        .select("ocel:oid")
        .unique()
    )
    reached_sources = (
        o2o
        .join(sources, left_on="ocel:oid", right_on="ocel:oid", how="inner")
        .join(reached_targets, left_on="ocel:oid_2", right_on="ocel:oid", how="inner")
        .select(pl.col("ocel:oid").n_unique().alias("n"))
        .collect()
        .item()
    )
    return float(reached_sources) / float(total)


registry.register_impl("kpi_conversion", "polars", sys.modules[__name__])
