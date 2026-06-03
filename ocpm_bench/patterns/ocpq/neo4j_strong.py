"""OCPQ via Neo4j: Cypher ports of Q1..Q7 (BPIC17-specific)."""

from __future__ import annotations

import sys
from datetime import timedelta

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs

_NEO4J_OCPQ: dict[str, str] = {
    "Q1": """
        MATCH (o:Application)
        OPTIONAL MATCH (e:A_Submitted)-[:E2O]->(o)
        WITH o, COUNT(e) AS eventCount
        RETURN o.id, eventCount <> 1
    """,
    "Q2": """
        MATCH (a1:Offer)
        MATCH (e1:O_Created)-[:E2O]->(a1)
        OPTIONAL MATCH (x:O_Returned)-[:E2O]->(a1)
        WITH a1, e1, COUNT(x) AS returnedCount
        RETURN a1.id, e1.id, returnedCount >= 1
    """,
    "Q3": """
        MATCH (e1:O_Returned)
        OPTIONAL MATCH (e1)-[:E2O]->(a1:Offer)
        WITH e1, COUNT(a1) AS offerCount
        RETURN e1.id, offerCount = 1
    """,
    "Q4": """
        MATCH (a1:Application)
        MATCH (e1:A_Accepted)-[:E2O]->(a1)
        OPTIONAL MATCH (a1)-[:O2O]->(o2:Offer)<-[:E2O]-(e2:O_Accepted)
            WHERE e1.time <= e2.time
        WITH a1, e1, COUNT(e2) AS acceptedCount
        RETURN a1.id, e1.id, acceptedCount >= 1
    """,
    "Q5": """
        MATCH (a1:Application)<-[:E2O]-(e1:A_Accepted)-[:E2O]->(a2:Case_R)
        OPTIONAL MATCH (a1)-[:O2O]->(o3:Offer)<-[:E2O]-(e2:O_Created)-[:E2O]->(c:Case_R)
        WITH a1, a2, e1,
             COUNT(e2) AS total,
             COUNT(CASE WHEN c.id = a2.id THEN 1 END) AS matched
        RETURN a1.id, a2.id, e1.id, (total = matched)
    """,
    # `duration.inSeconds` flattens diff into seconds+nanoseconds; avoids
    # calendar arithmetic from `duration.between` that breaks timedelta conversion.
    "Q6": """
        MATCH (e1:O_Created)-[:E2O]->(o:Offer)<-[:E2O]-(e2:O_Accepted)
        RETURN duration.inSeconds(e1.time, e2.time) AS d
        ORDER BY d DESC
        LIMIT 1
    """,
    "Q7": """
        MATCH (a1:Application)-[:O2O]->(a2:Offer)<-[:E2O]-(e2:O_Created)
        MATCH (a1)-[:O2O]->(a3:Offer)<-[:E2O]-(e3:O_Created)
        RETURN a1.id, a2.id, a3.id, e2.id, e3.id
    """,
}


def _neo4j_duration_to_timedelta(value) -> timedelta:
    if isinstance(value, timedelta):
        return value
    months = getattr(value, "months", 0) or 0
    if months:
        raise ValueError(
            "Neo4j Q6: month-precision durations cannot be losslessly converted"
        )
    days = getattr(value, "days", 0) or 0
    seconds = getattr(value, "seconds", 0) or 0
    nanos = getattr(value, "nanoseconds", 0) or 0
    return timedelta(days=days, seconds=seconds, microseconds=nanos // 1000)


def run(model, inputs: OCPQInputs) -> list[tuple]:
    cypher = _NEO4J_OCPQ.get(inputs.query_id)
    if cypher is None:
        raise NotImplementedError(
            f"No Neo4j Cypher port for OCPQ query {inputs.query_id!r}"
        )
    rows = model.execute_cypher(cypher)
    if inputs.query_id == "Q6":
        return [(_neo4j_duration_to_timedelta(r[0]),) for r in rows]
    return rows


registry.register_impl("ocpq", "neo4j_strong", sys.modules[__name__])
