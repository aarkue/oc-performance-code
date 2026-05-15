"""Variants via pandas: groupby + agg-tuple + value_counts."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.base import PerTypeInputs


def run(model: PandasModel, inputs: PerTypeInputs) -> list[tuple]:
    rel = model.relations
    sub = (
        rel.loc[rel["ocel:type"] == inputs.object_type,
                ["ocel:oid", "ocel:timestamp", "ocel:eid", "ocel:activity"]]
           .sort_values(["ocel:oid", "ocel:timestamp", "ocel:eid"])
    )
    traces = sub.groupby("ocel:oid", sort=False)["ocel:activity"].apply(tuple)
    return [(trace, int(count)) for trace, count in traces.value_counts().items()]


registry.register_impl("variants", "pandas", sys.modules[__name__])
