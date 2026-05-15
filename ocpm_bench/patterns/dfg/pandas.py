"""DFG via pandas: groupby + shift on the relations frame."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.base import PerTypeInputs


def run(model: PandasModel, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    rel = model.relations
    sub = (
        rel.loc[rel["ocel:type"] == inputs.object_type,
                ["ocel:oid", "ocel:timestamp", "ocel:eid", "ocel:activity"]]
           .sort_values(["ocel:oid", "ocel:timestamp", "ocel:eid"])
    )
    sub = sub.assign(next=sub.groupby("ocel:oid", sort=False)["ocel:activity"].shift(-1))
    sub = sub.dropna(subset=["next"])
    grouped = (
        sub.groupby(["ocel:activity", "next"], sort=False)
           .size()
           .reset_index(name="count")
    )
    return [(row[0], row[1], int(row[2])) for row in grouped.itertuples(index=False, name=None)]


registry.register_impl("dfg", "pandas", sys.modules[__name__])
