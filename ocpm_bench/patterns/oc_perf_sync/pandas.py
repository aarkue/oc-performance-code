"""Sync via Pandas: per-event span + delaying object."""

from __future__ import annotations

import sys

import pandas as pd

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns._perf_topk import perf_top_k

_US = pd.Timedelta(microseconds=1)


def run(model: PandasModel, _inputs) -> list[tuple[str, int, str]]:
    rel = model.relations[["ocel:eid", "ocel:oid", "ocel:timestamp"]].sort_values(
        ["ocel:oid", "ocel:timestamp", "ocel:eid"]
    )
    rel = rel.assign(
        pred_t=rel.groupby("ocel:oid", sort=False)["ocel:timestamp"].shift(1)
    )
    de = rel[rel["pred_t"].notna()]

    span = de.groupby("ocel:eid", sort=False)["pred_t"].agg(["min", "max"])
    span["sync_us"] = (span["max"] - span["min"]) // _US

    delaying = (
        de.sort_values(["ocel:eid", "pred_t", "ocel:oid"], ascending=[True, False, True])
        .drop_duplicates("ocel:eid", keep="first")[["ocel:eid", "ocel:oid"]]
    )
    out = span.reset_index()[["ocel:eid", "sync_us"]].merge(delaying, on="ocel:eid")
    k = perf_top_k()
    if k is not None:
        out = out.sort_values(["sync_us", "ocel:eid"], ascending=[False, True]).head(k)
    return [
        (str(e), int(s), str(o))
        for e, s, o in out.itertuples(index=False, name=None)
    ]


registry.register_impl("oc_perf_sync", "pandas", sys.modules[__name__])
