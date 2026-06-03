"""EKG via Polars: per-query frame implementations (BPIC17-specific)."""

from __future__ import annotations

import sys

import polars as pl

from ocpm_bench.harness import registry
from ocpm_bench.models.polars import PolarsModel
from ocpm_bench.patterns.base import OCPQInputs


def _q1(model: PolarsModel) -> list[tuple]:
    # A_Submitted events on Applications, with LoanGoal + timestamp.
    out = (
        model.relations.lazy()
        .filter(
            (pl.col("ocel:type") == "Application")
            & (pl.col("ocel:activity") == "A_Submitted")
        )
        .select([
            pl.col("ocel:oid").alias("application_id"),
            pl.col("ocel:eid").alias("event_id"),
            pl.col("ocel:timestamp").alias("submission"),
        ])
        .join(
            model.events.lazy().select(["ocel:eid", "LoanGoal"]),
            left_on="event_id",
            right_on="ocel:eid",
        )
        .select(["application_id", "event_id", "LoanGoal", "submission"])
        .unique()
        .collect()
    )
    return list(out.iter_rows())


def _q3(model: PolarsModel) -> list[tuple]:
    # O_Created at-or-before O_Cancelled on the same Offer (single-object DF = time order).
    rel = model.relations.lazy()
    created = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Created")
    ).select([
        pl.col("ocel:oid").alias("offer_id"),
        pl.col("ocel:eid").alias("o_created_id"),
        pl.col("ocel:timestamp").alias("t_created"),
    ])
    cancelled = rel.filter(
        (pl.col("ocel:type") == "Offer") & (pl.col("ocel:activity") == "O_Cancelled")
    ).select([
        pl.col("ocel:oid").alias("offer_id"),
        pl.col("ocel:eid").alias("o_cancelled_id"),
        pl.col("ocel:timestamp").alias("t_cancelled"),
    ])
    out = (
        created.join(cancelled, on="offer_id")
        .filter(pl.col("t_created") <= pl.col("t_cancelled"))
        .select(["offer_id", "o_created_id", "o_cancelled_id"])
        .unique()
        .collect()
    )
    return list(out.iter_rows())


def _q2(model: PolarsModel) -> list[tuple]:
    # Predecessor of each O_Created in the Offer's full event sequence (any activity).
    out = (
        model.relations.lazy()
        .filter(pl.col("ocel:type") == "Offer")
        .select([
            pl.col("ocel:oid").alias("offer_id"),
            pl.col("ocel:eid").alias("eid"),
            pl.col("ocel:activity").alias("act"),
            pl.col("ocel:timestamp").alias("t"),
        ])
        .sort(["offer_id", "t", "eid"])
        .with_columns(predecessor_id=pl.col("eid").shift(1).over("offer_id"))
        .filter(
            (pl.col("act") == "O_Created") & pl.col("predecessor_id").is_not_null()
        )
        .select([
            pl.col("offer_id"),
            pl.col("eid").alias("o_created_id"),
            pl.col("predecessor_id"),
        ])
        .collect()
    )
    return list(out.iter_rows())


_DISPATCH = {"Q1": _q1, "Q2": _q2, "Q3": _q3}


def run(model: PolarsModel, inputs: OCPQInputs) -> list[tuple]:
    fn = _DISPATCH.get(inputs.query_id)
    if fn is None:
        raise NotImplementedError(f"polars EKG: no implementation for {inputs.query_id}")
    return fn(model)


registry.register_impl("ekg", "polars", sys.modules[__name__])
