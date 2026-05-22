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

    sources_mask = objs["ocel:type"] == inputs.source_type
    total = int(sources_mask.sum())
    if total == 0:
        return 0.0
    source_ids = set(objs.loc[sources_mask, "ocel:oid"])

    reached_targets = set(rel.loc[
        (rel["ocel:activity"] == inputs.activity)
        & (rel["ocel:type"] == inputs.target_type),
        "ocel:oid",
    ])
    if not reached_targets:
        return 0.0

    reached_sources = set(
        o2o.loc[
            o2o["ocel:oid"].isin(source_ids) & o2o["ocel:oid_2"].isin(reached_targets),
            "ocel:oid",
        ]
    )
    return float(len(reached_sources)) / float(total)


registry.register_impl("kpi_conversion", "pandas", sys.modules[__name__])
