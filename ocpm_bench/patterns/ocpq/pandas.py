"""OCPQ Q1..Q7 in pandas. BPIC17-specific: hard-coded object/event type names."""

from __future__ import annotations

import sys

import pandas as pd

from ocpm_bench.harness import registry
from ocpm_bench.models.pandas import PandasModel
from ocpm_bench.patterns.base import OCPQInputs


def _objects(model: PandasModel, otype: str) -> pd.DataFrame:
    return (
        model.objects.loc[model.objects["ocel:type"] == otype, "ocel:oid"]
        .rename("ocel_id")
        .to_frame()
    )


def _events(model: PandasModel, activity: str) -> pd.DataFrame:
    return model.events.loc[
        model.events["ocel:activity"] == activity, ["ocel:eid", "ocel:timestamp"]
    ].rename(columns={"ocel:eid": "ocel_id", "ocel:timestamp": "ocel_time"})


def _e2o(model: PandasModel) -> pd.DataFrame:
    return (
        model.relations[["ocel:eid", "ocel:oid"]]
        .drop_duplicates()
        .rename(columns={"ocel:eid": "event_id", "ocel:oid": "object_id"})
    )


def _o2o(model: PandasModel) -> pd.DataFrame:
    return model.frames["o2o"][["ocel:oid", "ocel:oid_2"]].rename(
        columns={"ocel:oid": "source_id", "ocel:oid_2": "target_id"}
    )


def _q1(model: PandasModel) -> list[tuple]:
    apps = _objects(model, "Application").rename(columns={"ocel_id": "app_id"})
    submitted = _events(model, "A_Submitted")[["ocel_id"]].rename(columns={"ocel_id": "sub_id"})
    e2o = _e2o(model)

    step = apps.merge(e2o, left_on="app_id", right_on="object_id", how="left")
    step = step.merge(submitted, left_on="event_id", right_on="sub_id", how="left")
    counts = step.groupby("app_id")["sub_id"].count().reset_index(name="cnt")
    counts["satisfied"] = counts["cnt"] != 1
    return list(counts[["app_id", "satisfied"]].itertuples(index=False, name=None))


def _q2(model: PandasModel) -> list[tuple]:
    offers = _objects(model, "Offer").rename(columns={"ocel_id": "offer_id"})
    created = _events(model, "O_Created")[["ocel_id"]].rename(columns={"ocel_id": "created_id"})
    returned = _events(model, "O_Returned")[["ocel_id"]].rename(columns={"ocel_id": "returned_id"})
    e2o = _e2o(model)

    offer_created = (
        offers.merge(e2o, left_on="offer_id", right_on="object_id")
        .merge(created, left_on="event_id", right_on="created_id")[["offer_id", "created_id"]]
    )
    ret_counts = (
        e2o.merge(returned, left_on="event_id", right_on="returned_id")
        .groupby("object_id")["returned_id"]
        .count()
        .reset_index()
        .rename(columns={"object_id": "offer_id", "returned_id": "ret_count"})
    )

    result = offer_created.merge(ret_counts, on="offer_id", how="left")
    result["satisfied"] = result["ret_count"].fillna(0) >= 1
    return list(result[["offer_id", "created_id", "satisfied"]].itertuples(index=False, name=None))


def _q3(model: PandasModel) -> list[tuple]:
    returned = _events(model, "O_Returned")[["ocel_id"]].rename(columns={"ocel_id": "event_id"})
    offers = _objects(model, "Offer").rename(columns={"ocel_id": "offer_id"})
    e2o = _e2o(model)

    step = returned.merge(e2o, on="event_id", how="left")
    step = step.merge(offers, left_on="object_id", right_on="offer_id", how="left")
    counts = step.groupby("event_id")["offer_id"].count().reset_index(name="cnt")
    counts["satisfied"] = counts["cnt"] == 1
    return list(counts[["event_id", "satisfied"]].itertuples(index=False, name=None))


def _q4(model: PandasModel) -> list[tuple]:
    apps = _objects(model, "Application").rename(columns={"ocel_id": "app_id"})
    a_accepted = _events(model, "A_Accepted").rename(
        columns={"ocel_id": "evt_id", "ocel_time": "evt_time"}
    )
    offers = _objects(model, "Offer").rename(columns={"ocel_id": "offer_id"})
    o_accepted = _events(model, "O_Accepted").rename(
        columns={"ocel_id": "o_evt_id", "ocel_time": "o_time"}
    )
    e2o = _e2o(model)
    o2o = _o2o(model)

    app_events = (
        apps.merge(e2o, left_on="app_id", right_on="object_id")
        .merge(a_accepted, left_on="event_id", right_on="evt_id")[["app_id", "evt_id", "evt_time"]]
    )
    accepted_offers = (
        o2o.merge(offers, left_on="target_id", right_on="offer_id")
        .merge(e2o, left_on="offer_id", right_on="object_id")
        .merge(o_accepted, left_on="event_id", right_on="o_evt_id")[["source_id", "o_time"]]
        .drop_duplicates()
    )

    combined = app_events.merge(
        accepted_offers, left_on="app_id", right_on="source_id", how="left"
    )
    qualified = (
        combined.loc[combined["evt_time"] <= combined["o_time"], ["app_id", "evt_id"]]
        .drop_duplicates()
    )
    result = app_events.merge(qualified, on=["app_id", "evt_id"], how="left", indicator=True)
    result["satisfied"] = result["_merge"] == "both"
    return list(result[["app_id", "evt_id", "satisfied"]].itertuples(index=False, name=None))


def _q5(model: PandasModel) -> list[tuple]:
    apps = _objects(model, "Application").rename(columns={"ocel_id": "app_id"})
    a_accepted = _events(model, "A_Accepted")[["ocel_id"]].rename(columns={"ocel_id": "evt_id"})
    case_r = _objects(model, "Case_R").rename(columns={"ocel_id": "case_id"})
    offers = _objects(model, "Offer").rename(columns={"ocel_id": "offer_id"})
    o_created = _events(model, "O_Created")[["ocel_id"]].rename(columns={"ocel_id": "co_evt_id"})
    e2o = _e2o(model)
    o2o = _o2o(model)

    app_events = (
        apps.merge(e2o, left_on="app_id", right_on="object_id")
        .merge(a_accepted, left_on="event_id", right_on="evt_id")[["app_id", "evt_id"]]
    )
    e2o2 = e2o.rename(columns={"event_id": "ev2", "object_id": "ob2"})
    main = (
        app_events.merge(e2o2, left_on="evt_id", right_on="ev2")
        .merge(case_r, left_on="ob2", right_on="case_id")[["app_id", "case_id", "evt_id"]]
    )

    e2o3 = e2o.rename(columns={"event_id": "ev3", "object_id": "ob3"})
    created_offers = (
        o2o.merge(offers, left_on="target_id", right_on="offer_id")
        .merge(e2o, left_on="offer_id", right_on="object_id")
        .merge(o_created, left_on="event_id", right_on="co_evt_id")
        .merge(e2o3, left_on="co_evt_id", right_on="ev3")
        .merge(case_r.rename(columns={"case_id": "co_case_id"}),
               left_on="ob3", right_on="co_case_id")[["source_id", "co_case_id"]]
    )

    combined = main.merge(created_offers, left_on="app_id", right_on="source_id")
    combined["match"] = (combined["co_case_id"] == combined["case_id"]).astype(int)
    agg = (
        combined.groupby(["app_id", "case_id", "evt_id"])["match"]
        .min()
        .reset_index()
        .rename(columns={"match": "satisfied"})
    )
    return list(agg.itertuples(index=False, name=None))


def _q6(model: PandasModel) -> list[tuple]:
    offers = _objects(model, "Offer").rename(columns={"ocel_id": "offer_id"})
    o_created = _events(model, "O_Created").rename(
        columns={"ocel_id": "e1_id", "ocel_time": "e1_time"}
    )
    o_accepted = _events(model, "O_Accepted").rename(
        columns={"ocel_id": "e2_id", "ocel_time": "e2_time"}
    )
    e2o = _e2o(model)

    offer_e2o = offers.merge(e2o, left_on="offer_id", right_on="object_id")
    offer_created = offer_e2o.merge(o_created, left_on="event_id", right_on="e1_id")[
        ["offer_id", "e1_time"]
    ]
    offer_accepted = offer_e2o.merge(o_accepted, left_on="event_id", right_on="e2_id")[
        ["offer_id", "e2_time"]
    ]

    pairs = offer_created.merge(offer_accepted, on="offer_id")
    max_dur = (pairs["e2_time"] - pairs["e1_time"]).max()
    return [(max_dur,)]


def _q7(model: PandasModel) -> list[tuple]:
    apps = _objects(model, "Application").rename(columns={"ocel_id": "app_id"})
    offers = _objects(model, "Offer")
    o_created = _events(model, "O_Created")[["ocel_id"]].rename(columns={"ocel_id": "created_id"})
    e2o = _e2o(model)
    o2o = _o2o(model)

    branch = (
        apps.merge(o2o, left_on="app_id", right_on="source_id")
        .merge(offers, left_on="target_id", right_on="ocel_id")
        .merge(e2o, left_on="ocel_id", right_on="object_id")
        .merge(o_created, left_on="event_id", right_on="created_id")[
            ["app_id", "ocel_id", "created_id"]
        ]
    )

    result = branch.rename(columns={"ocel_id": "offer_2", "created_id": "created_2"}).merge(
        branch.rename(columns={"ocel_id": "offer_3", "created_id": "created_3"}),
        on="app_id",
    )
    return list(
        result[["app_id", "offer_2", "offer_3", "created_2", "created_3"]].itertuples(
            index=False, name=None
        )
    )


_DISPATCH: dict[str, object] = {
    "Q1": _q1, "Q2": _q2, "Q3": _q3, "Q4": _q4,
    "Q5": _q5, "Q6": _q6, "Q7": _q7,
}


def run(model: PandasModel, inputs: OCPQInputs) -> list[tuple]:
    # BPIC17-specific: the Q1..Q7 chains reference object/event type names
    # ("Application", "Offer", "A_Submitted", ...) directly. A non-BPIC17
    # OCEL would silently produce empty results rather than failing loudly.
    if "Application" not in model.objects["ocel:type"].unique():
        raise NotImplementedError(
            "pandas OCPQ impls are hand-ported for BPIC17 only "
            "(no 'Application' object type found in this OCEL)"
        )
    fn = _DISPATCH.get(inputs.query_id)
    if fn is None:
        raise NotImplementedError(f"pandas OCPQ: no implementation for {inputs.query_id}")
    return fn(model)  # type: ignore[operator]


registry.register_impl("ocpq", "pandas", sys.modules[__name__])
