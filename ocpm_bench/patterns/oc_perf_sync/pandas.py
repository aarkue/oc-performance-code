"""W1 via Pandas: df-edge based via per-object shift after sort."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel


def run(model: PandasModel, _inputs) -> list[tuple[str, int, int]]:
    rel = model.relations[
        ["ocel:eid", "ocel:activity", "ocel:timestamp", "ocel:oid"]
    ].sort_values(["ocel:oid", "ocel:timestamp", "ocel:eid"])

    rel = rel.assign(
        pred_t=rel.groupby("ocel:oid", sort=False)["ocel:timestamp"].shift(1)
    )
    de = rel[rel["pred_t"].notna()]

    per_event = de.groupby(["ocel:eid", "ocel:activity"], sort=False).agg(
        t_min=("pred_t", "min"),
        t_max=("pred_t", "max"),
    ).reset_index()
    per_event["span_s"] = (
        (per_event["t_max"] - per_event["t_min"]).dt.total_seconds().astype("int64")
    )

    out = per_event.groupby("ocel:activity", sort=False).agg(
        total=("span_s", "sum"),
        count=("span_s", "count"),
    ).reset_index()

    return [
        (str(a), int(t), int(c))
        for a, t, c in out.itertuples(index=False, name=None)
    ]


registry.register_impl("oc_perf_sync", "pandas", sys.modules[__name__])
