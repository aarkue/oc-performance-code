"""W2 via Pandas: df-edge based via per-object shift, argmax via sort + dedup."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel


def run(model: PandasModel, _inputs) -> list[tuple[str, str, int]]:
    rel = model.relations[
        ["ocel:eid", "ocel:activity", "ocel:timestamp", "ocel:oid", "ocel:type"]
    ].sort_values(["ocel:oid", "ocel:timestamp", "ocel:eid"])

    rel = rel.assign(
        pred_t=rel.groupby("ocel:oid", sort=False)["ocel:timestamp"].shift(1),
        pred_activity=rel.groupby("ocel:oid", sort=False)["ocel:activity"].shift(1),
    )
    de = rel[rel["pred_t"].notna()]

    picked = de.sort_values(
        ["ocel:eid", "pred_t", "ocel:oid"],
        ascending=[True, False, True],
    ).drop_duplicates(subset=["ocel:eid"], keep="first")

    out = (
        picked.groupby(["pred_activity", "ocel:type"], sort=False)
        .size()
        .reset_index(name="count")
    )
    return [
        (str(r["pred_activity"]), str(r["ocel:type"]), int(r["count"]))
        for _, r in out.iterrows()
    ]


registry.register_impl("oc_perf_delaying", "pandas", sys.modules[__name__])
