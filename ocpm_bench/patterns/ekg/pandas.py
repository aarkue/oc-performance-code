"""EKG via pandas: per-query frame implementations (BPIC17-specific)."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.base import OCPQInputs


def _q1(model: PandasModel) -> list[tuple]:
    rel = model.relations
    sub = rel.loc[
        (rel["ocel:type"] == "Application") & (rel["ocel:activity"] == "A_Submitted"),
        ["ocel:oid", "ocel:eid", "ocel:timestamp"],
    ].rename(
        columns={
            "ocel:oid": "application_id",
            "ocel:eid": "event_id",
            "ocel:timestamp": "submission",
        }
    )
    goals = model.events.loc[:, ["ocel:eid", "LoanGoal"]].rename(
        columns={"ocel:eid": "event_id"}
    )
    out = (
        sub.merge(goals, on="event_id", how="left")[
            ["application_id", "event_id", "LoanGoal", "submission"]
        ]
        .drop_duplicates()
    )
    return list(out.itertuples(index=False, name=None))


def _q3(model: PandasModel) -> list[tuple]:
    rel = model.relations
    created = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Created"),
        ["ocel:oid", "ocel:eid", "ocel:timestamp"],
    ].rename(
        columns={
            "ocel:oid": "offer_id",
            "ocel:eid": "o_created_id",
            "ocel:timestamp": "t_created",
        }
    )
    cancelled = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Cancelled"),
        ["ocel:oid", "ocel:eid", "ocel:timestamp"],
    ].rename(
        columns={
            "ocel:oid": "offer_id",
            "ocel:eid": "o_cancelled_id",
            "ocel:timestamp": "t_cancelled",
        }
    )
    merged = created.merge(cancelled, on="offer_id")
    out = merged.loc[
        merged["t_created"] <= merged["t_cancelled"],
        ["offer_id", "o_created_id", "o_cancelled_id"],
    ].drop_duplicates()
    return list(out.itertuples(index=False, name=None))


def _q2(model: PandasModel) -> list[tuple]:
    rel = model.relations
    oe = rel.loc[
        rel["ocel:type"] == "Offer",
        ["ocel:oid", "ocel:eid", "ocel:activity", "ocel:timestamp"],
    ].rename(
        columns={
            "ocel:oid": "offer_id",
            "ocel:eid": "eid",
            "ocel:activity": "act",
            "ocel:timestamp": "t",
        }
    ).sort_values(["offer_id", "t", "eid"])
    oe["predecessor_id"] = oe.groupby("offer_id", sort=False)["eid"].shift(1)
    out = oe.loc[
        (oe["act"] == "O_Created") & oe["predecessor_id"].notna(),
        ["offer_id", "eid", "predecessor_id"],
    ].rename(columns={"eid": "o_created_id"})
    return list(out.itertuples(index=False, name=None))


_DISPATCH = {"Q1": _q1, "Q2": _q2, "Q3": _q3}


def run(model: PandasModel, inputs: OCPQInputs) -> list[tuple]:
    fn = _DISPATCH.get(inputs.query_id)
    if fn is None:
        raise NotImplementedError(f"pandas EKG: no implementation for {inputs.query_id}")
    return fn(model)


registry.register_impl("ekg", "pandas", sys.modules[__name__])
