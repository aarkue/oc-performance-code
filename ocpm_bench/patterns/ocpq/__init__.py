"""OCPQ pattern: bundled Q1..Q7 query files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import OCPQInputs, OutputSchema, PatternContract
from ocpm_bench.patterns.ocpq._q6 import to_milliseconds

_OUTPUT = OutputSchema(kind="tuple_set", columns=[])

_DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "corpus"


def _corpus_dir() -> Path:
    env = os.environ.get("OCPQ_CORPUS_DIR")
    return Path(env) if env else _DEFAULT_CORPUS_DIR


def _instances(dataset) -> list[tuple[str, Any]]:
    corpus = _corpus_dir()
    if not corpus.is_dir():
        raise FileNotFoundError(
            f"OCPQ corpus not found at {corpus}. Set OCPQ_CORPUS_DIR to override."
        )
    out: list[tuple[str, Any]] = []
    for qdir in sorted(corpus.glob("Q*")):
        if not qdir.is_dir():
            continue
        sql_path = qdir / "sql.txt"
        tree_path = qdir / "ocpq-tree.json"
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


_BOOL_LAST_COL = {"Q1", "Q2", "Q3", "Q4", "Q5"}
_DURATION_LAST_COL = {"Q6"}


def normalize_ocpq_row(row: tuple, qid: str) -> tuple[str, ...]:
    """Canonicalize one result row to a tuple of strings across all engines."""
    if qid in _BOOL_LAST_COL and len(row) >= 1:
        head = tuple(str(v) for v in row[:-1])
        tail = row[-1]
        if isinstance(tail, bool):
            norm = "true" if tail else "false"
        elif isinstance(tail, int) and tail in (0, 1):
            norm = "true" if tail else "false"
        elif isinstance(tail, str) and tail.lower() in ("true", "false", "1", "0"):
            norm = "true" if tail.lower() in ("true", "1") else "false"
        else:
            norm = str(tail)
        return (*head, norm)
    if qid in _DURATION_LAST_COL and len(row) >= 1:
        head = tuple(str(v) for v in row[:-1])
        try:
            ms = to_milliseconds(row[-1])
        except (TypeError, ValueError):
            return (*head, str(row[-1]))
        return (*head, str(ms))
    return tuple(str(v) for v in row)


# LinkedOCEL emits rows in Rust's native shape; SQL/Cypher engines return SQL
# shape. Reshape Rust to SQL untimed.
_LINKED_OCEL_PROJECT_ROW = {
    "Q1": lambda r: (r[0], not r[1]),  # satisfied -> violated
    "Q7": lambda r: r[:-1],            # drop trailing satisfied
}


def _post_process(raw, inputs: OCPQInputs, model):
    qid = inputs.query_id
    if model.name == "linked_ocel":
        if qid == "Q6":
            # Rust emits one row per binding (max_dur, satisfied); SQL emits
            # a single (max_dur,) row.
            raw = [(raw[0][0],)] if raw else []
        elif qid in _LINKED_OCEL_PROJECT_ROW:
            proj = _LINKED_OCEL_PROJECT_ROW[qid]
            raw = [proj(row) for row in raw]
    return [normalize_ocpq_row(row, qid) for row in raw]


CONTRACT = PatternContract(
    name="ocpq",
    output=_OUTPUT,
    instances=_instances,
    oracle_model="linked_ocel",
    post_process=_post_process,
)

registry.register_pattern(CONTRACT)
