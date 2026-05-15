"""Side-effect imports that populate the harness registry."""

# Datasets
import ocpm_bench.datasets.bpic17

# Models
import ocpm_bench.models.duckdb
import ocpm_bench.models.duckdb_strong_rels
import ocpm_bench.models.kuzu
import ocpm_bench.models.kuzu_weak
import ocpm_bench.models.linked_ocel
import ocpm_bench.models.pandas
import ocpm_bench.models.polars
import ocpm_bench.models.sqlite_mem
import ocpm_bench.models.sqlite_mem_strong_rels

# Pattern: dfg
import ocpm_bench.patterns.dfg
import ocpm_bench.patterns.dfg._sql
import ocpm_bench.patterns.dfg._sql_strong_rels
import ocpm_bench.patterns.dfg.kuzu
import ocpm_bench.patterns.dfg.linked_ocel
import ocpm_bench.patterns.dfg.pandas
import ocpm_bench.patterns.dfg.polars

# Pattern: dfg_prim
import ocpm_bench.patterns.dfg_prim

# Pattern: ocpq
import ocpm_bench.patterns.ocpq
import ocpm_bench.patterns.ocpq._sql
import ocpm_bench.patterns.ocpq.kuzu
import ocpm_bench.patterns.ocpq.linked_ocel
import ocpm_bench.patterns.ocpq.pandas
import ocpm_bench.patterns.ocpq.polars

# Pattern: variants
import ocpm_bench.patterns.variants
import ocpm_bench.patterns.variants._sql
import ocpm_bench.patterns.variants._sql_strong_rels
import ocpm_bench.patterns.variants.kuzu
import ocpm_bench.patterns.variants.linked_ocel
import ocpm_bench.patterns.variants.pandas
import ocpm_bench.patterns.variants.polars

# Pattern: variants_prim
import ocpm_bench.patterns.variants_prim
