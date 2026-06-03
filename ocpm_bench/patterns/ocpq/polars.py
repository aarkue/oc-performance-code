"""OCPQ Q1..Q7 in native Polars. BPIC17-specific: hard-coded type/activity names.

Mirrors the pandas impl 1:1 (same filters, joins, and output column order) so
the two dataframe engines do the same work and are directly comparable. Unlike
the relational engines, Polars does NOT reuse the corpus SQL: it runs idiomatic
``pl.DataFrame`` expressions over the cached frames, all inside the timed
``run`` (no SQLContext schema-adapter shaping in an untimed ``pre_run``).

Q6: Polars stores ocel:timestamp as Datetime, so subtraction yields a Duration;
``iter_rows`` converts the max to a timedelta, handled by ``_q6.to_milliseconds``.
"""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.base import OCPQInputs


def _q1(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    sub_per_app = (
        rel.filter(
            (pl.col("ocel:type") == "Application")
            & (pl.col("ocel:activity") == "A_Submitted")
        )
        .group_by("ocel:oid")
        .agg(pl.len().alias("cnt"))
    )
    apps = model.objects.filter(pl.col("ocel:type") == "Application").select("ocel:oid")
    out = apps.join(sub_per_app, on="ocel:oid", how="left").with_columns(
        pl.col("cnt").fill_null(0)
    )
    return [(oid, c != 1) for oid, c in out.select("ocel:oid", "cnt").iter_rows()]


def _q2(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    offer_created = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Created")
    ).select("ocel:oid", "ocel:eid")
    returned_counts = (
        rel.filter(
            (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Returned")
        )
        .group_by("ocel:oid")
        .agg(pl.len().alias("ret_count"))
    )
    out = offer_created.join(returned_counts, on="ocel:oid", how="left").with_columns(
        pl.col("ret_count").fill_null(0)
    )
    return [
        (oid, eid, c >= 1)
        for oid, eid, c in out.select("ocel:oid", "ocel:eid", "ret_count").iter_rows()
    ]


def _q3(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    offers_per_return = (
        rel.filter(
            (pl.col("ocel:activity") == "O_Returned") & (pl.col("ocel:type") == "Offer")
        )
        .group_by("ocel:eid")
        .agg(pl.len().alias("cnt"))
    )
    all_returned = model.events.filter(
        pl.col("ocel:activity") == "O_Returned"
    ).select("ocel:eid")
    out = all_returned.join(offers_per_return, on="ocel:eid", how="left").with_columns(
        pl.col("cnt").fill_null(0)
    )
    return [(eid, c == 1) for eid, c in out.select("ocel:eid", "cnt").iter_rows()]


def _q4(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    a_acc = rel.filter(
        (pl.col("ocel:type") == "Application")
        & (pl.col("ocel:activity") == "A_Accepted")
    ).select(
        pl.col("ocel:oid").alias("app_id"),
        pl.col("ocel:eid").alias("evt_id"),
        pl.col("ocel:timestamp").alias("evt_time"),
    )
    o_acc = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Accepted")
    ).select(
        pl.col("ocel:oid").alias("offer_id"),
        pl.col("ocel:timestamp").alias("o_time"),
    )
    links = o2o.select(
        pl.col("ocel:oid").alias("app_id"),
        pl.col("ocel:oid_2").alias("offer_id"),
    )
    candidate = a_acc.join(links, on="app_id").join(o_acc, on="offer_id")
    qualified = (
        candidate.filter(pl.col("evt_time") <= pl.col("o_time"))
        .select("app_id", "evt_id")
        .unique()
        .with_columns(pl.lit(value=True).alias("satisfied"))
    )
    out = (
        a_acc.select("app_id", "evt_id")
        .join(qualified, on=["app_id", "evt_id"], how="left")
        .with_columns(pl.col("satisfied").fill_null(value=False))
    )
    return list(out.select("app_id", "evt_id", "satisfied").iter_rows())


def _q5(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    app_acc = rel.filter(
        (pl.col("ocel:type") == "Application")
        & (pl.col("ocel:activity") == "A_Accepted")
    ).select(
        pl.col("ocel:oid").alias("app_id"),
        pl.col("ocel:eid").alias("evt_id"),
    )
    case_on_evt = rel.filter(pl.col("ocel:type") == "Case_R").select(
        pl.col("ocel:oid").alias("case_id"),
        pl.col("ocel:eid").alias("evt_id"),
    )
    main = app_acc.join(case_on_evt, on="evt_id").select("app_id", "case_id", "evt_id")

    app_to_offer = o2o.select(
        pl.col("ocel:oid").alias("app_id"),
        pl.col("ocel:oid_2").alias("offer_id"),
    )
    offer_created = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Created")
    ).select(
        pl.col("ocel:oid").alias("offer_id"),
        pl.col("ocel:eid").alias("co_evt_id"),
    )
    case_via_created = rel.filter(pl.col("ocel:type") == "Case_R").select(
        pl.col("ocel:oid").alias("co_case_id"),
        pl.col("ocel:eid").alias("co_evt_id"),
    )
    offer_case = (
        app_to_offer.join(offer_created, on="offer_id")
        .join(case_via_created, on="co_evt_id")
        .select("app_id", "co_case_id")
    )

    combined = main.join(offer_case, on="app_id").with_columns(
        (pl.col("co_case_id") == pl.col("case_id")).alias("match")
    )
    out = combined.group_by(["app_id", "case_id", "evt_id"]).agg(
        pl.col("match").all().alias("satisfied")
    )
    return list(out.select("app_id", "case_id", "evt_id", "satisfied").iter_rows())


def _q6(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    offer_created = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Created")
    ).select(pl.col("ocel:oid"), pl.col("ocel:timestamp").alias("e1_time"))
    offer_accepted = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Accepted")
    ).select(pl.col("ocel:oid"), pl.col("ocel:timestamp").alias("e2_time"))
    pairs = offer_created.join(offer_accepted, on="ocel:oid")
    max_dur = pairs.select((pl.col("e2_time") - pl.col("e1_time")).alias("d"))["d"].max()
    return [(max_dur,)]


def _q7(model: PolarsModel) -> list[tuple]:
    rel = model.relations
    o2o = model.frames["o2o"]
    apps = model.objects.filter(pl.col("ocel:type") == "Application").select(
        pl.col("ocel:oid").alias("app_id")
    )
    links = o2o.select(
        pl.col("ocel:oid").alias("app_id"),
        pl.col("ocel:oid_2").alias("offer_id"),
    ).join(apps, on="app_id")
    offer_created = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Created")
    ).select(
        pl.col("ocel:oid").alias("offer_id"),
        pl.col("ocel:eid").alias("created_id"),
    )
    branch = links.join(offer_created, on="offer_id").select(
        "app_id", "offer_id", "created_id"
    )
    out = branch.rename({"offer_id": "offer_2", "created_id": "created_2"}).join(
        branch.rename({"offer_id": "offer_3", "created_id": "created_3"}),
        on="app_id",
    )
    return list(
        out.select("app_id", "offer_2", "offer_3", "created_2", "created_3").iter_rows()
    )


_DISPATCH = {
    "Q1": _q1, "Q2": _q2, "Q3": _q3, "Q4": _q4,
    "Q5": _q5, "Q6": _q6, "Q7": _q7,
}


def run(model: PolarsModel, inputs: OCPQInputs) -> list[tuple]:
    fn = _DISPATCH.get(inputs.query_id)
    if fn is None:
        raise NotImplementedError(
            f"polars OCPQ: no implementation for {inputs.query_id}"
        )
    return fn(model)


registry.register_impl("ocpq", "polars", sys.modules[__name__])
