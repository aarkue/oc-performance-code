"""EKG corpus pattern: the original Esser-Fahland graph queries as OCPQ trees.

Reuses the OCPQ oracle (``evaluate_ocpq``) and engine query forms but reads its
own ``corpus/`` so EKG is reported separately from OCPQ Q1-Q7.

Output contract (after dropping ``evaluate_ocpq``'s trailing ``satisfied`` bool
and pinning timestamps to microseconds):
- Q1: ``(application_id, event_id, loan_goal, timestamp)``
- Q2: ``(offer_id, o_created_id, predecessor_id)``
- Q3: ``(offer_id, o_created_id, o_cancelled_id)``
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import normalize_timestamp
from ocpm_bench.patterns.base import OCPQInputs, OutputSchema, PatternContract

_OUTPUT = OutputSchema(kind="tuple_set", columns=[])
_DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

# Zero-based indices of timestamp columns in each query's contract shape.
_TS_COLS: dict[str, tuple[int, ...]] = {"Q1": (3,)}


def _corpus_dir() -> Path:
    env = os.environ.get("EKG_CORPUS_DIR")
    return Path(env) if env else _DEFAULT_CORPUS_DIR


def _instances(_dataset) -> list[tuple[str, Any]]:
    corpus = _corpus_dir()
    if not corpus.is_dir():
        raise FileNotFoundError(
            f"EKG corpus not found at {corpus}. Set EKG_CORPUS_DIR to override."
        )
    out: list[tuple[str, Any]] = []
    for qdir in sorted(corpus.glob("Q*")):
        if not qdir.is_dir():
            continue
        sql_path = qdir / "sql.txt"
        tree_path = qdir / "ocpq-tree.json"
        # A query activates only once both its tree (oracle) and SQL exist.
        if not (sql_path.is_file() and tree_path.is_file()):
            continue
        qid = qdir.name
        body: dict[str, Any] = {
            "sql": sql_path.read_text(),
            "tree_json": tree_path.read_text(),
        }
        for override in sorted(qdir.glob("sql-*.txt")):
            body[override.stem] = override.read_text()
        out.append((qid, OCPQInputs(query_id=qid, query_body=body)))
    return out


def _canon_ts(value: Any) -> str:
    if isinstance(value, str):
        s = value
    elif hasattr(value, "isoformat"):
        s = value.isoformat()
    else:
        s = str(value)
    s = normalize_timestamp(s)
    base, _, frac = s.partition(".")
    # Pin microsecond precision: Neo4j renders 9-digit nanoseconds, the others 6.
    return f"{base}.{(frac + '000000')[:6]}"


def _canon_scalar(v: Any) -> str:
    # A missing attribute is None for the oracle/SQL/Polars/Cypher engines but
    # float NaN for pandas; map both to one sentinel so engines compare equal.
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v)


def _canon_row(row: tuple, qid: str) -> tuple[str, ...]:
    ts_cols = _TS_COLS.get(qid, ())
    return tuple(
        _canon_ts(v) if i in ts_cols else _canon_scalar(v)
        for i, v in enumerate(row)
    )


def _post_process(raw, inputs: OCPQInputs, model):
    qid = inputs.query_id
    rows = raw
    if model.name == "linked_ocel":
        # evaluate_ocpq appends a trailing `satisfied` bool per binding; EKG
        # queries restrict via filters, so every returned binding is satisfied.
        rows = [r[:-1] for r in rows if r[-1]]
    return [_canon_row(row, qid) for row in rows]


CONTRACT = PatternContract(
    name="ekg",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
