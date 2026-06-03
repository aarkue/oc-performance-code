"""OCPQ Q1..Q7 in pandas. BPIC17-specific: hard-coded object/event type names."""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.base import OCPQInputs


def _q1(model: PandasModel) -> list[tuple]:
    rel = model.relations
    sub_per_app = (
        rel.loc[
            (rel["ocel:type"] == "Application") & (rel["ocel:activity"] == "A_Submitted"),
            "ocel:oid",
        ]
        .value_counts()
        .rename("cnt")
        .reset_index()
    )
    apps = model.objects.loc[
        model.objects["ocel:type"] == "Application", ["ocel:oid"]
    ]
    out = apps.merge(sub_per_app, on="ocel:oid", how="left")
    out["cnt"] = out["cnt"].fillna(0).astype("int64")
    return [(oid, c != 1) for oid, c in out.itertuples(index=False, name=None)]


def _q2(model: PandasModel) -> list[tuple]:
    rel = model.relations
    offer_created = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Created"),
        ["ocel:oid", "ocel:eid"],
    ]
    returned_counts = (
        rel.loc[
            (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Returned"),
            "ocel:oid",
        ]
        .value_counts()
        .rename("ret_count")
        .reset_index()
    )
    out = offer_created.merge(returned_counts, on="ocel:oid", how="left")
    out["ret_count"] = out["ret_count"].fillna(0)
    return [
        (oid, eid, int(c) >= 1)
        for oid, eid, c in out.itertuples(index=False, name=None)
    ]


def _q3(model: PandasModel) -> list[tuple]:
    rel = model.relations
    offers_per_return = (
        rel.loc[
            (rel["ocel:activity"] == "O_Returned") & (rel["ocel:type"] == "Offer"),
            "ocel:eid",
        ]
        .value_counts()
        .rename("cnt")
        .reset_index()
    )
    all_returned = model.events.loc[
        model.events["ocel:activity"] == "O_Returned", ["ocel:eid"]
    ]
    out = all_returned.merge(offers_per_return, on="ocel:eid", how="left")
    out["cnt"] = out["cnt"].fillna(0).astype("int64")
    return [(eid, c == 1) for eid, c in out.itertuples(index=False, name=None)]


def _q4(model: PandasModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    a_acc = rel.loc[
        (rel["ocel:type"] == "Application") & (rel["ocel:activity"] == "A_Accepted"),
        ["ocel:oid", "ocel:eid", "ocel:timestamp"],
    ].rename(
        columns={"ocel:oid": "app_id", "ocel:eid": "evt_id", "ocel:timestamp": "evt_time"}
    )
    o_acc = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Accepted"),
        ["ocel:oid", "ocel:timestamp"],
    ].rename(columns={"ocel:oid": "offer_id", "ocel:timestamp": "o_time"})
    links = o2o[["ocel:oid", "ocel:oid_2"]].rename(
        columns={"ocel:oid": "app_id", "ocel:oid_2": "offer_id"}
    )
    candidate = a_acc.merge(links, on="app_id").merge(o_acc, on="offer_id")
    qualified = (
        candidate.loc[
            candidate["evt_time"] <= candidate["o_time"], ["app_id", "evt_id"]
        ]
        .drop_duplicates()
        .assign(satisfied=True)
    )
    out = a_acc[["app_id", "evt_id"]].merge(
        qualified, on=["app_id", "evt_id"], how="left"
    )
    out["satisfied"] = out["satisfied"].fillna(False).astype(bool)
    return list(out.itertuples(index=False, name=None))


def _q5(model: PandasModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    app_acc = rel.loc[
        (rel["ocel:type"] == "Application") & (rel["ocel:activity"] == "A_Accepted"),
        ["ocel:oid", "ocel:eid"],
    ].rename(columns={"ocel:oid": "app_id", "ocel:eid": "evt_id"})
    case_on_evt = rel.loc[
        rel["ocel:type"] == "Case_R", ["ocel:oid", "ocel:eid"]
    ].rename(columns={"ocel:oid": "case_id", "ocel:eid": "evt_id"})
    main = app_acc.merge(case_on_evt, on="evt_id")[["app_id", "case_id", "evt_id"]]

    app_to_offer = o2o[["ocel:oid", "ocel:oid_2"]].rename(
        columns={"ocel:oid": "app_id", "ocel:oid_2": "offer_id"}
    )
    offer_created = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Created"),
        ["ocel:oid", "ocel:eid"],
    ].rename(columns={"ocel:oid": "offer_id", "ocel:eid": "co_evt_id"})
    case_via_created = rel.loc[
        rel["ocel:type"] == "Case_R", ["ocel:oid", "ocel:eid"]
    ].rename(columns={"ocel:oid": "co_case_id", "ocel:eid": "co_evt_id"})
    offer_case = (
        app_to_offer
        .merge(offer_created, on="offer_id")
        .merge(case_via_created, on="co_evt_id")[["app_id", "co_case_id"]]
    )

    combined = main.merge(offer_case, on="app_id")
    combined["match"] = (combined["co_case_id"] == combined["case_id"]).astype(int)
    out = (
        combined.groupby(["app_id", "case_id", "evt_id"], sort=False)["match"]
        .min()
        .reset_index()
        .rename(columns={"match": "satisfied"})
    )
    return list(out.itertuples(index=False, name=None))


def _q6(model: PandasModel) -> list[tuple]:
    rel = model.relations
    offer_created = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Created"),
        ["ocel:oid", "ocel:timestamp"],
    ].rename(columns={"ocel:timestamp": "e1_time"})
    offer_accepted = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Accepted"),
        ["ocel:oid", "ocel:timestamp"],
    ].rename(columns={"ocel:timestamp": "e2_time"})
    pairs = offer_created.merge(offer_accepted, on="ocel:oid")
    max_dur = (pairs["e2_time"] - pairs["e1_time"]).max()
    return [(max_dur,)]


def _q7(model: PandasModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    apps = model.objects.loc[
        model.objects["ocel:type"] == "Application", ["ocel:oid"]
    ].rename(columns={"ocel:oid": "app_id"})
    links = o2o[["ocel:oid", "ocel:oid_2"]].rename(
        columns={"ocel:oid": "app_id", "ocel:oid_2": "offer_id"}
    ).merge(apps, on="app_id")
    offer_created = rel.loc[
        (rel["ocel:type"] == "Offer") & (rel["ocel:activity"] == "O_Created"),
        ["ocel:oid", "ocel:eid"],
    ].rename(columns={"ocel:oid": "offer_id", "ocel:eid": "created_id"})
    branch = links.merge(offer_created, on="offer_id")[["app_id", "offer_id", "created_id"]]
    out = branch.rename(columns={"offer_id": "offer_2", "created_id": "created_2"}).merge(
        branch.rename(columns={"offer_id": "offer_3", "created_id": "created_3"}),
        on="app_id",
    )
    return list(
        out[["app_id", "offer_2", "offer_3", "created_2", "created_3"]].itertuples(
            index=False, name=None
        )
    )


_DISPATCH: dict[str, object] = {
    "Q1": _q1, "Q2": _q2, "Q3": _q3, "Q4": _q4,
    "Q5": _q5, "Q6": _q6, "Q7": _q7,
}


def run(model: PandasModel, inputs: OCPQInputs) -> list[tuple]:
    fn = _DISPATCH.get(inputs.query_id)
    if fn is None:
        raise NotImplementedError(f"pandas OCPQ: no implementation for {inputs.query_id}")
    return fn(model)  # type: ignore[operator]


registry.register_impl("ocpq", "pandas", sys.modules[__name__])
