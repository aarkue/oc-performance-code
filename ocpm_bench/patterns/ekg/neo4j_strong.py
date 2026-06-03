"""EKG via Neo4j (strong): per-query Cypher (BPIC17-specific).

``toString(e.time)`` is canonicalized to microsecond precision by the pattern's
post-processing (Neo4j renders 9-digit nanoseconds).
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs

_NEO4J_EKG: dict[str, str] = {
    "Q1": """
        MATCH (e:A_Submitted)-[:E2O]->(o:Application)
        RETURN o.id, e.id, e.LoanGoal, toString(e.time)
    """,
    "Q3": """
        MATCH (e1:O_Created)-[:E2O]->(o:Offer)<-[:E2O]-(e2:O_Cancelled)
        WHERE e1.time <= e2.time
        RETURN o.id, e1.id, e2.id
    """,
    # DF edge into O_Created: e2 is its immediate predecessor on the Offer.
    "Q2": """
        MATCH (e2)-[df:DF {EntityType: 'Offer'}]->(e1:O_Created)
        RETURN df.id AS offer_id, e1.id, e2.id
    """,
}


def run(model, inputs: OCPQInputs) -> list[tuple]:
    cypher = _NEO4J_EKG.get(inputs.query_id)
    if cypher is None:
        raise NotImplementedError(f"No Neo4j Cypher for EKG {inputs.query_id!r}")
    return model.execute_cypher(cypher)


registry.register_impl("ekg", "neo4j_strong", sys.modules[__name__])
