"""EKG via Kuzu: per-query Cypher (BPIC17-specific).

Both Kuzu models carry event attributes (e.g. LoanGoal): the strong model as
typed node properties from r4pm's typed export, the weak model as STRING columns
on its single ``Event`` table (see ``models.kuzu_weak``). The weak queries mirror
the strong ones, swapping typed node labels for a ``type`` property filter.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs

_KUZU_EKG: dict[str, str] = {
    "Q1": """
        MATCH (e:A_Submitted)-[:E2O]->(o:Application)
        RETURN o.id, e.id, e.LoanGoal, e.time
    """,
    "Q3": """
        MATCH (e1:O_Created)-[:E2O]->(o:Offer)<-[:E2O]-(e2:O_Cancelled)
        WHERE e1.time <= e2.time
        RETURN o.id, e1.id, e2.id
    """,
    # Directly-follows via the materialized per-Offer DF edge: e2 is O_Created's
    # immediate predecessor on the Offer (DF edge whose destination is e1).
    "Q2": """
        MATCH (e2)-[df:DF]->(e1:O_Created)
        WHERE df.EntityType = 'Offer'
        RETURN df.id AS offer_id, e1.id AS o_created_id, e2.id AS predecessor_id
    """,
}

# Weak schema: single Event/Object labels, activity/type carried in the `type`
# property and event attributes (LoanGoal) as STRING columns on Event.
_KUZU_WEAK_EKG: dict[str, str] = {
    "Q1": """
        MATCH (e:Event)-[:E2O]->(o:Object)
        WHERE e.type = 'A_Submitted' AND o.type = 'Application'
        RETURN o.id, e.id, e.LoanGoal, e.time
    """,
    "Q3": """
        MATCH (e1:Event)-[:E2O]->(o:Object)<-[:E2O]-(e2:Event)
        WHERE e1.type = 'O_Created' AND o.type = 'Offer'
          AND e2.type = 'O_Cancelled' AND e1.time <= e2.time
        RETURN o.id, e1.id, e2.id
    """,
    "Q2": """
        MATCH (e2:Event)-[df:DF]->(e1:Event)
        WHERE df.EntityType = 'Offer' AND e1.type = 'O_Created'
        RETURN df.id AS offer_id, e1.id AS o_created_id, e2.id AS predecessor_id
    """,
}


def run(model, inputs: OCPQInputs) -> list[tuple]:
    queries = _KUZU_WEAK_EKG if model.name == "kuzu_weak" else _KUZU_EKG
    cypher = queries.get(inputs.query_id)
    if cypher is None:
        raise NotImplementedError(f"No Kuzu Cypher for EKG {inputs.query_id!r}")
    return model.execute_cypher(cypher)


registry.register_impl("ekg", "kuzu", sys.modules[__name__])
registry.register_impl("ekg", "kuzu_weak", sys.modules[__name__])
