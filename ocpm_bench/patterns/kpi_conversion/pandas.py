"""K2 (conversion rate) via Pandas.

Source -> O2O -> Target -> E2O <- Event with activity.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.kpi_conversion import KPIConversionInputs


def run(model: PandasModel, inputs: KPIConversionInputs) -> float:
    objs = model.objects
    rel = model.relations
    o2o = model.frames["o2o"]

    sources = objs.loc[objs["ocel:type"] == inputs.source_type, ["ocel:oid"]]
    total = len(sources)
    if total == 0:
        return 0.0
    reached_targets = (
        rel.loc[
            (rel["ocel:activity"] == inputs.activity)
            & (rel["ocel:type"] == inputs.target_type),
            ["ocel:oid"],
        ]
        .drop_duplicates()
        .rename(columns={"ocel:oid": "ocel:oid_2"})
    )
    reached = o2o.merge(sources, on="ocel:oid", how="inner").merge(
        reached_targets, on="ocel:oid_2", how="inner"
    )
    return float(reached["ocel:oid"].nunique()) / float(total)


registry.register_impl("kpi_conversion", "pandas", sys.modules[__name__])
