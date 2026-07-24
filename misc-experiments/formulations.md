# Alternative Workload Formulations

The benchmark reports one implementation per engine-workload pair: the fastest
formulation we arrived at. This file documents the alternatives that were tried
and discarded, so the selection is inspectable rather than implicit.

Not every entry has a preserved code artifact. Where a variant was replaced
in-place, the commit is given and the superseded version can be recovered from
the repository history.

## Object-centric queries (P2)

**Polars: SQL translation vs. native dataframe code.** The OCPQ corpus was first
evaluated through `pl.SQLContext`, reusing the same SQL as the relational
engines with a per-query schema adapter built in an untimed `pre_run`. It was
later reimplemented in native Polars expressions, which is what the paper
measures. The SQL variant lives in the history of
`ocpm_bench/patterns/ocpq/polars.py` together with the seven deleted
`ocpm_bench/patterns/ocpq/corpus/Q*/sql-polars.txt` files.

**Per-engine SQL overrides.** The corpus keeps `sql.txt` as the shared
formulation and adds engine-specific overrides where a rewrite was faster, see
`corpus/Q*/sql-sqlite_mem.txt` and `corpus/Q*/sql-{sqlite_mem,duckdb}_strong_rels.txt`.
Polars' SQL frontend resolves columns through flattened subqueries, so the
overrides for Q4-Q7 additionally pre-rename `ocel_id`/`ocel_time` per registered
table.

## Object-centric performance analysis (P3)

**Neo4j: aggregation over E2O vs. materialized DF edges.** Sync time was
formulated both as an aggregation over shared-object predecessors and over
materialized `:DF` edges; commit `52ebaf9` records two further Cypher variants
of the DF-edge version. The DF-edge formulation is what the paper measures, and
the DF edges are materialized at load time.

**Delaying object as a separate pass.** Sync time and the delaying object were
initially two patterns (`oc_perf_delaying`, removed in `47e9095`) and are now
computed in a single pass per engine, which avoids traversing the predecessor
relation twice.

**Rust4PM: binding result transfer.** The per-event results were first
returned through `serde_json::Value` that the host re-serialized and
Python parsed with `json.loads`. Serializing straight to JSON bytes and parsing
with `orjson` cut sync by about 15% and sojourn by about 25% at unchanged
output. At 1.2M rows this conversion dominated the cell instead of the traversal itself.
Fixed upstream.

## Control flow (P1)

**Traversal primitives vs. engine-native queries.** `ocpm_bench/patterns/dfg_prim`
and `ocpm_bench/patterns/variants_prim` implement DFG and variants purely from
the `PrimitiveAccess` interface (`get_objects_of_type`, `get_events_of_object`,
`get_timestamp`, `get_activity`), i.e. identical Python code for every engine.
They are far slower than the engine-native formulations the paper reports and
are kept as a reference point for the cost of per-call traversal.

## Engine configuration

**Kuzu: result fetching.** Fetching query results per row via `get_next()` was
replaced by a bulk `get_as_pl().iter_rows()` fetch, which is 18-34% faster on the
query workloads at identical types and values.

**Neo4j: page cache and timestamp index.** Neo4j 5 defaults
`server.memory.pagecache.size` to a flat 512 MiB, not a fraction of RAM (verified
via `SHOW SETTINGS` on an otherwise unconfigured server).
The BPIC17 database is ~3.6 GB, so an unconfigured server cannot hold the database in cache and reads
from disk during measurement.
Thus, we increased this parameter, so that all engines are not memory-bound.


**Kuzu: on-disk vs. in-memory database.** See
[kuzu_mem_vs_disk.py](./kuzu_mem_vs_disk.py). On-disk is not slower than
`:memory:` on the DFG workload, and in fact slightly faster.

**Relational engines: timestamp index.** The OCEL 2.0 export indexes identifier
columns and both endpoints of the relation tables, but no timestamps. We measured
SQLite and DuckDB with an additional `ocel_time` index on every per-activity
event table, against the unmodified export.

No measurable effect. Sums over the corpus queries, N=3 warm runs, 8 threads,
`+ts / baseline`:

| workload | engine | baseline | +ts index | ratio |
|---|---|---|---|---|
| OCPQ Q1-Q7 | SQLite | 253.7 s | 247.8 s | 0.98 |
| EKG Q1-Q3 | SQLite | 293.5 s | 300.6 s | 1.02 |
| OCPQ Q1-Q7 | DuckDB | 405.5 ms | 417.1 ms | 1.03 |
| EKG Q1-Q3 | DuckDB | 162.7 ms | 160.7 ms | 0.99 |
| Sojourn | DuckDB | 185.4 ms | 189.8 ms | 1.02 |

All ratios within +-3% in both directions. The paper's Neo4j timestamp index is
therefore not mirrored on the relational engines. A cross-session comparison had
suggested ~12% for SQLite EKG; repeating both arms in one session removed it, so
that was drift, not signal.

**Schema typing.** Weak vs. strong entity typing is not a discarded alternative
but a reported sub-study, see the paper and the `*_weak` / `*_strong_rels`
models.
