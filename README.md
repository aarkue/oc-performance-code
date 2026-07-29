# ocpm-bench

Benchmark harness for object-centric process data models.

The benchmark currently covers these access patterns:

- P1 control flow: directly-follows graphs (`dfg`), trace variants (`variants`)
- P2 queries: OCPQ Q1 to Q7 (`ocpq`), EKG corpus Q1 to Q3 (`ekg`)
- P3 OC-Perf: per-event synchronization time + delaying object (`oc_perf_sync`), per-event sojourn time (`oc_perf_sojourn`)
- P4 BI/KPI: activity x object-type heatmap (`kpi_heatmap`), conversion rate (`kpi_conversion`)

## Models

Schema choices are encoded in the model id.

- `linked_ocel`: r4pm's SlimLinkedOCEL representation (also used in OCPQ tool, so combined)
- `sqlite_mem`, `duckdb`: OCEL 2.0 relational schema
- `sqlite_mem_strong_rels`, `duckdb_strong_rels`: relational schema with per-type relation tables
- `kuzu`: typed Kuzu graph export
- `kuzu_weak`: Kuzu graph with generic `Event` and `Object` nodes
- `neo4j_strong`: Neo4j 5 with per-type node labels + constant `:E2O` / `:O2O` rels
- `polars`, `pandas`: DataFrame representation (PM4Py-style)

Cached exports live under `code/cache/<dataset>/<model>/`.

## Setup

Requires Python 3.14.

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv venv .venv --python 3.14
# Activate the venv:
#   Linux/macOS:        source .venv/bin/activate
#   Windows PowerShell: .venv\Scripts\Activate.ps1
#   Windows cmd.exe:    .venv\Scripts\activate.bat
uv pip install -e ".[dev]"
# r4pm requires a custom build with OCPQ support; the normal PyPI release does not include it.
# Install the prerelease (with the polars extra) from https://github.com/aarkue/r4pm/releases or use:
# uv pip install --prerelease=allow "r4pm[polars]==0.5.5a6"
```

Or with the standard library `venv` + `pip` (Python 3.14 must already be installed):

```bash
python -m venv .venv
# Activate the venv:
#   Linux/macOS:        source .venv/bin/activate
#   Windows PowerShell: .venv\Scripts\Activate.ps1
#   Windows cmd.exe:    .venv\Scripts\activate.bat
pip install -e ".[dev]"
# Same r4pm caveat as above, e.g.:
# pip install --prerelease=allow "r4pm[polars]==0.5.5a6"
```

BPIC17 OCEL source file:

- bundled with the repo at `code/data/bpic17/bpic2017-ocel2.canonical.json.gz` (~54 MB gzipped)
- loaded directly from the gzip; no manual decompression needed
- override with `OCPM_BPIC17_PATH=/path/to/file.json[.gz]` to point at a different copy

### Dataset provenance

The measured file is derived from the OCEL 1.0 `.jsonocel` by Khayatbashi, Hartig
and Jalali, "BPI Challenge 2017 (OCEL)", 4TU.ResearchData (2023),
https://data.4tu.nl/datasets/6889ca3f-97cf-459a-b630-3b0b0d8664b5 (itself derived
from the BPIC17 event knowledge graph). Two scripts reproduce it:

```bash
# OCEL 1.0 -> OCEL 2.0, adding object-to-object relations
python scripts/convert_ocel1_to_ocel2.py BPIC17.jsonocel bpic2017-ocel2.json
# break tied timestamps to make each event timestamp unique
python scripts/canonicalize.py bpic2017-ocel2.json data/bpic17/bpic2017-ocel2.canonical.json
```

The OCPQ Q1 to Q7 query files used by the benchmark are bundled under
`ocpm_bench/patterns/ocpq/corpus/`.

## Paper results

The measurements and generated tables used for the paper are included:

- `results/paper-all.jsonl`: raw per-instance measurements
- `results/tables/main.{tex,pdf}`: main runtime table
- `results/tables/typing.{tex,pdf}`: entity-typing table
- `results/tables/typing_rels.{tex,pdf}`: relation-typing table

## Alternative formulations and side experiments

The benchmark reports one implementation per engine-workload pair, the fastest
formulation we arrived at.
Alternatives that were tested are documented in
[`misc-experiments/`](misc-experiments/README.md).

## Setup with Docker

A `Dockerfile` and `docker-compose.yml` are provided as an alternative to the
local Python install. The image pins Python 3.14, installs the project in
editable mode, and installs the r4pm prerelease that bundles OCPQ support.

Build once:

```bash
docker compose build
```

Run a one-shot benchmark (results and cache are bind-mounted to the host so
output is persisted across runs):

```bash
docker compose run --rm bench matrix --prepare --spec configs/dfg-small.yaml
```

Run the plotting script (writes PNG and PDF next to the input JSONL in the
mounted `results/` directory):

```bash
docker compose run --rm --entrypoint python bench scripts/plot_results.py results/dfg-small.jsonl
```

The same image also works for development. The `dev` service bind-mounts the
whole `code/` directory on top of `/app`, so edits to `ocpm_bench/`, `configs/`,
or `scripts/` are picked up live (the install is editable):

```bash
docker compose run --rm dev          # interactive bash shell
# inside the container:
ocpm-bench matrix --prepare --spec configs/dfg-small.yaml
ruff check ocpm_bench
```

On Docker Desktop (macOS/Windows), raise the VM memory to at least 8 GB
(Settings -> Resources). Larger datasets will OOM at the default 2 GB cap.

Note on benchmark numbers: Docker adds overhead, prefer a native install for
paper-grade numbers.

## Setup with Apptainer

Single-file SIF bundles Neo4j 5, Python 3.14, r4pm and the bench. Install
apptainer locally (https://apptainer.org/docs/admin/main/installation.html) , then:

```bash
# Build locally
apptainer build --fakeroot ocpm-bench.sif Apptainer.def

# Copy to server
# ....

# Run on a server/compute node
mkdir -p $PWD/run/{neo4j-data,neo4j-import,results,cache}
apptainer run --writable-tmpfs \
  --bind $PWD/run/neo4j-data:/data \
  --bind $PWD/run/neo4j-import:/var/lib/neo4j/import \
  --bind $PWD/run/results:/app/results \
  --bind $PWD/run/cache:/app/cache \
  ocpm-bench.sif matrix --prepare --spec configs/dfg-small.yaml
```

Two jobs on the same node collide on bolt port `7687` (apptainer shares the
host network); use `--exclusive` node allocation under SLURM.

## Running

Run one cell:

```bash
ocpm-bench run --model linked_ocel --pattern dfg --dataset bpic17
```

Run a matrix:

```bash
ocpm-bench matrix --prepare --spec configs/dfg-small.yaml
```

`--prepare` runs an untimed `model.setup()` for every unique (model, dataset)
pair in the spec before measurement begins (kuzu cache build, CSV export,
neo4j data load). Per-cell setup in the measurement subprocesses then hits
warm state, so `cell_timeout_seconds` bounds the query work rather than the
one-time load.

Standalone prepare (e.g. after wiping `cache/`):

```bash
ocpm-bench prepare --spec configs/paper-all.yaml
```

Common specs:

| spec                               | contents                                       |
| ---------------------------------- | ---------------------------------------------- |
| `paper-{small,all}.yaml`           | all engines x DFG + variants + OCPQ (combined) |
| `dfg-{small,paper}.yaml`           | engine-native DFG                              |
| `variants-{small,paper}.yaml`      | engine-native trace variants                   |
| `ocpq-{small,paper}.yaml`          | OCPQ Q1 to Q7                                  |
| `perf-{small,paper}.yaml`          | OC-Perf Sync + Sojourn                         |
| `kpi-{small,paper}.yaml`           | KPI K1 (heatmap) + K2 (conversion)             |
| `dfg_prim-{small,paper}.yaml`      | DFG via shared `PrimitiveAccess`               |
| `variants_prim-{small,paper}.yaml` | trace variants via shared `PrimitiveAccess`    |
| `strong_rels-ab.yaml`              | DuckDB strong-rels and Kuzu weak comparisons   |

Each matrix cell runs in a separate subprocess and appends JSONL rows to the
configured `results_path`.

## Patterns

Two distinct pattern flavors exist:

**Engine-native** (`dfg`, `variants`, `ocpq`): each model has its own idiomatic
implementation (e.g., SQL for SQLite/DuckDB, Cypher for Kuzu, DataFrame ops for
Polars/pandas, r4pm functions for LinkedOCEL). Idea: Measure each engine in its natural
element.

**Primitive-access** (`dfg_prim`, `variants_prim`): all models run the same
Python code through the `PrimitiveAccess` protocol (`get_objects_of_type`,
`get_events_of_object`, `get_timestamp`, `get_activity`). Isolates raw
data-access cost from engine-native optimization.

`ocpq` uses per-engine query ports:

- SQL engines run corpus SQL, with optional `sql-<model>.txt` overrides
- LinkedOCEL evaluates the OCPQ tree through r4pm (OCPQ Tool Evaluation Engine)
- Kuzu runs custom Cypher
- Polars uses `pl.SQLContext`
- pandas has BPIC17-specific implementations

## Timing

Only `impl.run()` is timed.

Untimed setup and normalization hooks:

- `prepare` phase: one-time `model.setup()` per (model, dataset) pair
  (kuzu cache builds, CSV exports, neo4j LOAD CSV) before measurement
- `model.setup()` inside the cell subprocess: hits the warm cache from above
- `impl.pre_run(model)`: per-cell preparation, for example Polars OCPQ context setup
- `pattern.post_process(raw, inputs, model)`: result-shape normalization
- `canonicalize(raw, schema)`: oracle comparison format

Result rows include warm samples, one cold sample, the model's reported
`model_bytes` (in-memory or on-disk footprint depending on the model), and the
process `rss_bytes_after_setup`. RSS is a process-level memory signal, not a
pure model-size measurement.

### Known measurement limitations

- **`model_bytes` is not cross-engine comparable.** Each engine returns a
  different concept under the same field name: on-disk DB file/dir size for
  `duckdb`/`kuzu`/`neo4j_strong`, in-memory page bytes for `sqlite_mem`
  (`:memory:`), in-RAM frame footprint for `pandas`/`polars`, and the source
  OCEL file size for `linked_ocel` (not its in-process Rust structure).
- **RSS excludes the Neo4j server.** `rss_bytes_after_setup` is the Python
  process RSS only. For embedded engines it includes the engine; for
  `neo4j_strong`, which runs in a separate JVM/container, it excludes the
  actual storage. A unified container-level RSS would be needed for an
  apples-to-apples comparison.
- **RSS is contaminated for `kuzu`/`kuzu_weak`/`neo4j_strong`.**
  `_build_name_info` calls `r4pm.import_item("SlimLinkedOCEL", ...)` for
  type-name discovery and then `remove_item`s it; the allocator typically
  does not return pages to the OS, so the released ~1.8 GB sticks in RSS.
  Reported RSS therefore overstates these engines' true memory cost by
  roughly that amount.
- **One cold sample per cell.** Cold-vs-warm is informative only after
  cross-cell aggregation; individual cell cold/warm ratios are noisy.

Potential extensions:

- Replace `model_bytes` with a single uniform metric (container/process RSS
  delta, or in-memory bytes measured from outside the engine's API).
- Move the `_build_name_info` r4pm call into the subprocess `prepare` phase
  so it does not pollute the engine RSS measurement.
- Capture multiple cold samples per cell (fresh subprocess per sample) for a
  proper cold-start distribution rather than a single point per cell.

Pattern outputs are compared against the LinkedOCEL oracle unless the pattern
declares another oracle model. Paper runs fail on incorrect cells by default.
Use `--allow-incorrect` or `allow_incorrect: true` only for exploratory runs.

## Architecture

Each model, dataset, and pattern registers itself by calling `registry.register_*`
at module level. `registrations.py` is the single file that imports all of these
modules for their side-effects.
It is the only file you need to touch to add a new component. When `run_cell(model, pattern, dataset, ...)` is called, the
registry resolves the triple to a concrete `CellSpec`, sets up the model, then
times `impl.run(model, inputs)` for each query instance. Correctness is checked
by re-running the same instance against the oracle model (LinkedOCEL by default)
and comparing canonicalized outputs.

## Extending

### Adding a dataset

```python
# ocpm_bench/datasets/mydataset.py
import r4pm
from functools import cached_property
from ocpm_bench.datasets.base import Dataset
from ocpm_bench.harness import registry

class MyDataset(Dataset):
    name = "mydataset"
    source_path = "/path/to/mydataset.json"

    def fetch(self) -> None:
        if not Path(self.source_path).exists():
            raise FileNotFoundError(f"dataset not found at {self.source_path}")

    @cached_property
    def _object_types(self) -> list[str]:
        self.fetch()
        oid = r4pm.import_item("SlimLinkedOCEL", self.source_path)
        try:
            return list(r4pm.bindings.locel_get_ob_types(oid))
        finally:
            r4pm.remove_item(oid)

    def object_types(self) -> list[str]:
        return list(self._object_types)

registry.register_dataset("mydataset", MyDataset)
```

Then add `import ocpm_bench.datasets.mydataset` to `registrations.py`.

### Adding a model

A model needs five methods plus a `name` attribute. Implement `PrimitiveAccess`
(from `models/primitives.py`) as well to get `dfg_prim` and `variants_prim` for
free (i.e., no per-pattern files needed).

```python
# ocpm_bench/models/mymodel.py
from ocpm_bench.harness import registry
from ocpm_bench.models.primitives import PrimitiveAccess

class MyModel(PrimitiveAccess):  # or just object if skipping primitives
    name = "mymodel"

    def setup(self, dataset) -> None: ...   # load/connect
    def teardown(self) -> None: ...         # close/release
    def size_on_disk(self) -> int: ...      # model representation footprint in bytes
    def reset_caches(self) -> None: ...     # drop engine caches between timing reps
    def library_versions(self) -> dict[str, str]: ...

    # PrimitiveAccess methods (if implementing the protocol):
    def get_objects_of_type(self, object_type: str) -> list[str]: ...
    def get_events_of_object(self, object_id: str) -> list[str]: ...
    def get_timestamp(self, event_id: str) -> ...: ...
    def get_activity(self, event_id: str) -> str: ...

registry.register_model("mymodel", MyModel)
```

Add `import ocpm_bench.models.mymodel` to `registrations.py`, then register
per-pattern impls for any engine-native patterns (see below).

### Adding an engine-native impl for an existing pattern

```python
# ocpm_bench/patterns/dfg/mymodel.py
import sys
from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import PerTypeInputs

def run(model, inputs: PerTypeInputs) -> list[tuple[str, str, int]]:
    # ...your idiomatic implementation...
    return [(src, tgt, cnt), ...]

registry.register_impl("dfg", "mymodel", sys.modules[__name__])
```

Add `import ocpm_bench.patterns.dfg.mymodel` to `registrations.py`.

### Adding a new engine-native pattern

1. Create `ocpm_bench/patterns/mypattern/__init__.py` with a `PatternContract`:

```python
import sys
from typing import Any
from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import PatternContract, PerTypeInputs, OutputSchema

def _instances(dataset) -> list[tuple[str, Any]]:
    return [(ot, PerTypeInputs(object_type=ot)) for ot in dataset.object_types()]

CONTRACT = PatternContract(
    name="mypattern",
    output=OutputSchema(kind="tuple_set", columns=["col1", "col2"]),
    instances=_instances,
)
registry.register_pattern(CONTRACT)
```

2. Add one `ocpm_bench/patterns/mypattern/<model>.py` per model with `run()` + `register_impl`.
3. Add all imports to `registrations.py`.

### Adding a primitive-access pattern

A single `run()` function using only `PrimitiveAccess` methods runs across all models:

```python
# ocpm_bench/patterns/mypattern_prim/__init__.py
import sys
from typing import Any
from ocpm_bench.harness import registry
from ocpm_bench.patterns.base import PatternContract, PerTypeInputs, OutputSchema

def run(model, inputs: PerTypeInputs) -> list[tuple]:
    # Use only PrimitiveAccess methods: model.get_objects_of_type(), etc.
    ...

_PRIM_MODELS = (
    "linked_ocel", "sqlite_mem", "duckdb",
    "sqlite_mem_strong_rels", "duckdb_strong_rels",
    "kuzu", "polars", "pandas",
)
for _m in _PRIM_MODELS:
    registry.register_impl("mypattern_prim", _m, sys.modules[__name__])

CONTRACT = PatternContract(
    name="mypattern_prim",
    output=OutputSchema(kind="tuple_set", columns=["col1", "col2"]),
    instances=lambda ds: [(ot, PerTypeInputs(object_type=ot)) for ot in ds.object_types()],
)
registry.register_pattern(CONTRACT)
```

Add `import ocpm_bench.patterns.mypattern_prim` to `registrations.py`.

## Plotting

```bash
python scripts/plot_results.py results/ocpq-paper.jsonl
```

The script writes PNG and PDF files next to the input JSONL.

## Regenerating the paper tables

`scripts/make_table.py` consumes one or more JSONL files (rows filtered by
their `pattern` field) and writes the main results table plus two optional
typing sub-study tables.

```bash
python scripts/make_table.py \
    --input results/paper-all.jsonl \
    --output results/tables/main.tex \
    --typing-output results/tables/typing.tex \
    --typing-rels-output results/tables/typing_rels.tex

scripts/make_table_pdfs.sh
```

Flags:

- `--input <jsonl> [<jsonl> ...]` -- one or more JSONLs; rows are combined.
- `--output <path>` -- main table.
- `--typing-output <path>` -- node-typing table: weak -> default schema
  (typed entity tables), speedup factor per corpus. SQLite, DuckDB, Kuzu.
- `--typing-rels-output <path>` -- edge-typing table: default -> strong_rels
  schema (per-pair relation tables). SQLite and DuckDB only.
- `--inner-stat {mean,median}` -- within-cell aggregation (default `mean`).
- `--on-incorrect {drop,include,error}` -- handling of `correct=False` rows.
- `--no-color`, `--no-bold` -- disable column tinting / winner bold.
- `--draft-note "..."` -- prepend a red `Draft:` disclaimer to the caption.

Cells without a JSONL row render as `--`; this covers both "unimplemented"
and "timed out" (the harness kills cells exceeding `cell_timeout_seconds`
and writes no row).
