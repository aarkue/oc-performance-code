"""Sojourn via Pandas: per-event time since the latest predecessor."""

from __future__ import annotations

import sys

import pandas as pd

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns._perf_topk import perf_top_k

_US = pd.Timedelta(microseconds=1)


def run(model: PandasModel, _inputs) -> list[tuple[str, int]]:
    rel = model.relations[["ocel:eid", "ocel:oid", "ocel:timestamp"]].sort_values(
        ["ocel:oid", "ocel:timestamp", "ocel:eid"]
    )
    rel = rel.assign(
        pred_t=rel.groupby("ocel:oid", sort=False)["ocel:timestamp"].shift(1)
    )
    de = rel[rel["pred_t"].notna()]

    g = de.groupby("ocel:eid", sort=False).agg(
        e_t=("ocel:timestamp", "max"), latest=("pred_t", "max")
    ).reset_index()
    g["sojourn_us"] = (g["e_t"] - g["latest"]) // _US
    out = g[["ocel:eid", "sojourn_us"]]
    k = perf_top_k()
    if k is not None:
        out = out.sort_values(["sojourn_us", "ocel:eid"], ascending=[False, True]).head(k)
    return [
        (str(e), int(s))
        for e, s in out.itertuples(index=False, name=None)
    ]


registry.register_impl("oc_perf_sojourn", "pandas", sys.modules[__name__])
