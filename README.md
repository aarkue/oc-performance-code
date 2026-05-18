# ocpm-bench

Benchmark harness for object-centric process data models.

The benchmark currently covers three access patterns:

- directly-follows graphs (`dfg`)
- trace variants (`variants`)
- OCPQ Q1 to Q7 (`ocpq`)

## Models

Schema choices are encoded in the model id.

- `linked_ocel`: r4pm's SlimLinkedOCEL representation (also used in OCPQ tool, so combined)
- `sqlite_mem`, `duckdb`: OCEL 2.0 relational schema
- `sqlite_mem_strong_rels`, `duckdb_strong_rels`: relational schema with per-type relation tables
- `kuzu`: typed Kuzu graph export
- `kuzu_weak`: Kuzu graph with generic `Event` and `Object` nodes
- `polars`, `pandas`: DataFrame representation (PM4Py-style)

Cached exports live under `code/cache/<dataset>/<model>/`.

## Setup

Requires Python 3.14.

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv venv .venv --python 3.14
source .venv/bin/activate
uv pip install -e ".[dev]"
# r4pm requires a custom build with OCPQ support; the normal PyPI release does not include it.
# See https://github.com/aarkue/r4pm/releases or use
# uv pip install "r4pm==0.5.5a2"
# or uv pip install <path-to-r4pm-wheel> if you downloaded a wheel (e.g., from GitHub)
```

Or with the standard library `venv` + `pip` (Python 3.14 must already be installed):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Same r4pm caveat as above, e.g.:
# pip install "r4pm==0.5.5a2"
# or pip install <path-to-r4pm-wheel>
```

BPIC17 OCEL source file:

- bundled with the repo at `code/data/bpic17/bpic2017-ocel2.canonical.json.gz` (~54 MB gzipped)
- loaded directly from the gzip; no manual decompression needed
- override with `OCPM_BPIC17_PATH=/path/to/file.json[.gz]` to point at a different copy

The OCPQ Q1 to Q7 query files used by the benchmark are bundled under
`ocpm_bench/patterns/ocpq/corpus/`.

## Running

Run one cell:

```bash
ocpm-bench run --model linked_ocel --pattern dfg --dataset bpic17
```

Run a matrix:

```bash
ocpm-bench matrix --spec configs/dfg-small.yaml
```

Common specs:

| spec                               | contents                                     |
| ---------------------------------- | -------------------------------------------- |
| `dfg-{small,paper}.yaml`           | engine-native DFG                            |
| `variants-{small,paper}.yaml`      | engine-native trace variants                 |
| `ocpq-{small,paper}.yaml`          | OCPQ Q1 to Q7                                |
| `dfg_prim-{small,paper}.yaml`      | DFG via shared `PrimitiveAccess`             |
| `variants_prim-{small,paper}.yaml` | trace variants via shared `PrimitiveAccess`  |
| `strong_rels-ab.yaml`              | DuckDB strong-rels and Kuzu weak comparisons |

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

- `impl.pre_run(model)`: per-cell preparation, for example Polars OCPQ context setup
- `pattern.post_process(raw, inputs, model)`: result-shape normalization
- `canonicalize(raw, schema)`: oracle comparison format

Result rows include warm samples, one cold sample, the model's reported
`model_bytes` (in-memory or on-disk footprint depending on the model), and the
process `rss_bytes_after_setup`. RSS is a process-level memory signal, not a
pure model-size measurement.

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