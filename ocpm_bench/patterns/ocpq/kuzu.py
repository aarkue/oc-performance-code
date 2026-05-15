"""OCPQ via Kuzu: per-row Cypher ports of Q1..Q7 (BPIC17-specific).

For oracle parity with the SQL impls we emit one row per binding (the
corpus `neo4j-cypher.txt` returns aggregate counts, which would not match).

Schema (from r4pm's `export_ocel_to_kuzudb_typed`):
- One NODE per event type and per object type.
- REL `E2O` (event -> object) and REL `O2O` (object -> object).
- BPIC17's O2O direction is Application -> Offer.
"""

from __future__ import annotations

import sys

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs

_KUZU_OCPQ: dict[str, str] = {
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
    # NB: r4pm's typed export records BPIC17's O2O as Application -> Offer
    # (parent -> child), opposite to the EKG corpus's Offer -> Application.
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
    # Q6: subtract at INTERVAL precision (a `to_epoch_ms` round-trip would
    # truncate each timestamp to ms before subtraction, losing precision
    # vs. the DuckDB/LinkedOCEL paths). Kuzu hands the result back as a
    # `datetime.timedelta`, normalized by `_q6.to_milliseconds`.
    "Q6": """
        MATCH (e1:O_Created)-[:E2O]->(o:Offer)<-[:E2O]-(e2:O_Accepted)
        RETURN MAX(e2.time - e1.time)
    """,
    "Q7": """
        MATCH (a1:Application)-[:O2O]->(a2:Offer)<-[:E2O]-(e2:O_Created)
        MATCH (a1)-[:O2O]->(a3:Offer)<-[:E2O]-(e3:O_Created)
        RETURN a1.id, a2.id, a3.id, e2.id, e3.id
    """,
}

_KUZU_WEAK_OCPQ: dict[str, str] = {
    "Q1": """
        MATCH (o:Object)
        WHERE o.type = 'Application'
        OPTIONAL MATCH (e:Event)-[:E2O]->(o)
        WITH o, COUNT(CASE WHEN e.type = 'A_Submitted' THEN 1 END) AS eventCount
        RETURN o.id, eventCount <> 1
    """,
    "Q2": """
        MATCH (a1:Object)
        WHERE a1.type = 'Offer'
        MATCH (e1:Event)-[:E2O]->(a1)
        WHERE e1.type = 'O_Created'
        OPTIONAL MATCH (x:Event)-[:E2O]->(a1)
        WITH a1, e1,
             COUNT(CASE WHEN x.type = 'O_Returned' THEN 1 END) AS returnedCount
        RETURN a1.id, e1.id, returnedCount >= 1
    """,
    "Q3": """
        MATCH (e1:Event)
        WHERE e1.type = 'O_Returned'
        OPTIONAL MATCH (e1)-[:E2O]->(a1:Object)
        WITH e1, COUNT(CASE WHEN a1.type = 'Offer' THEN 1 END) AS offerCount
        RETURN e1.id, offerCount = 1
    """,
    "Q4": """
        MATCH (a1:Object)
        WHERE a1.type = 'Application'
        MATCH (e1:Event)-[:E2O]->(a1)
        WHERE e1.type = 'A_Accepted'
        OPTIONAL MATCH (a1)-[:O2O]->(o2:Object)<-[:E2O]-(e2:Event)
        WITH a1, e1,
             COUNT(CASE
                 WHEN o2.type = 'Offer'
                  AND e2.type = 'O_Accepted'
                  AND e1.time <= e2.time THEN 1
             END) AS acceptedCount
        RETURN a1.id, e1.id, acceptedCount >= 1
    """,
    "Q5": """
        MATCH (a1:Object)<-[:E2O]-(e1:Event)-[:E2O]->(a2:Object)
        WHERE a1.type = 'Application'
          AND e1.type = 'A_Accepted'
          AND a2.type = 'Case_R'
        OPTIONAL MATCH (a1)-[:O2O]->(o3:Object)<-[:E2O]-(e2:Event)-[:E2O]->(c:Object)
        WITH a1, a2, e1,
             COUNT(CASE
                 WHEN o3.type = 'Offer'
                  AND e2.type = 'O_Created'
                  AND c.type = 'Case_R' THEN 1
             END) AS total,
             COUNT(CASE
                 WHEN o3.type = 'Offer'
                  AND e2.type = 'O_Created'
                  AND c.type = 'Case_R'
                  AND c.id = a2.id THEN 1
             END) AS matched
        RETURN a1.id, a2.id, e1.id, (total = matched)
    """,
    "Q6": """
        MATCH (e1:Event)-[:E2O]->(o:Object)<-[:E2O]-(e2:Event)
        WHERE e1.type = 'O_Created'
          AND o.type = 'Offer'
          AND e2.type = 'O_Accepted'
        RETURN MAX(e2.time - e1.time)
    """,
    "Q7": """
        MATCH (a1:Object)-[:O2O]->(a2:Object)<-[:E2O]-(e2:Event)
        MATCH (a1)-[:O2O]->(a3:Object)<-[:E2O]-(e3:Event)
        WHERE a1.type = 'Application'
          AND a2.type = 'Offer'
          AND a3.type = 'Offer'
          AND e2.type = 'O_Created'
          AND e3.type = 'O_Created'
        RETURN a1.id, a2.id, a3.id, e2.id, e3.id
    """,
}


def run(model, inputs: OCPQInputs) -> list[tuple]:
    queries = _KUZU_WEAK_OCPQ if model.name == "kuzu_weak" else _KUZU_OCPQ
    cypher = queries.get(inputs.query_id)
    if cypher is None:
        raise NotImplementedError(
            f"No Kuzu Cypher port for OCPQ query {inputs.query_id!r}"
        )
    return model.execute_cypher(cypher)


registry.register_impl("ocpq", "kuzu", sys.modules[__name__])
registry.register_impl("ocpq", "kuzu_weak", sys.modules[__name__])
