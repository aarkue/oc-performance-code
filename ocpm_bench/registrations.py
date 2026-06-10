"""Side-effect imports that populate the harness registry."""

# Datasets
import ocpm_bench.datasets.bpic17

# Models
import ocpm_bench.models.duckdb
import ocpm_bench.models.duckdb_strong_rels
import ocpm_bench.models.duckdb_weak
import ocpm_bench.models.kuzu
import ocpm_bench.models.kuzu_weak
import ocpm_bench.models.linked_ocel
import ocpm_bench.models.neo4j_strong
import ocpm_bench.models.pandas
import ocpm_bench.models.polars
import ocpm_bench.models.sqlite_mem
import ocpm_bench.models.sqlite_mem_strong_rels
import ocpm_bench.models.sqlite_mem_weak

# Pattern: dfg
import ocpm_bench.patterns.dfg
import ocpm_bench.patterns.dfg._sql
import ocpm_bench.patterns.dfg._sql_strong_rels
import ocpm_bench.patterns.dfg.kuzu
import ocpm_bench.patterns.dfg.linked_ocel
import ocpm_bench.patterns.dfg.neo4j_strong
import ocpm_bench.patterns.dfg.pandas
import ocpm_bench.patterns.dfg.polars

# Pattern: dfg_prim
import ocpm_bench.patterns.dfg_prim

# Pattern: ekg
import ocpm_bench.patterns.ekg
import ocpm_bench.patterns.ekg._sql
import ocpm_bench.patterns.ekg.kuzu
import ocpm_bench.patterns.ekg.linked_ocel
import ocpm_bench.patterns.ekg.neo4j_strong
import ocpm_bench.patterns.ekg.pandas
import ocpm_bench.patterns.ekg.polars

# Pattern: kpi_conversion (P4 / K2)
import ocpm_bench.patterns.kpi_conversion
import ocpm_bench.patterns.kpi_conversion._sql
import ocpm_bench.patterns.kpi_conversion.kuzu
import ocpm_bench.patterns.kpi_conversion.linked_ocel
import ocpm_bench.patterns.kpi_conversion.neo4j_strong
import ocpm_bench.patterns.kpi_conversion.pandas
import ocpm_bench.patterns.kpi_conversion.polars

# Pattern: kpi_heatmap (P4 / K1)
import ocpm_bench.patterns.kpi_heatmap
import ocpm_bench.patterns.kpi_heatmap._sql
import ocpm_bench.patterns.kpi_heatmap.kuzu
import ocpm_bench.patterns.kpi_heatmap.linked_ocel
import ocpm_bench.patterns.kpi_heatmap.neo4j_strong
import ocpm_bench.patterns.kpi_heatmap.pandas
import ocpm_bench.patterns.kpi_heatmap.polars

# Pattern: oc_perf_sojourn (P3 / Sojourn)
import ocpm_bench.patterns.oc_perf_sojourn
import ocpm_bench.patterns.oc_perf_sojourn._sql
import ocpm_bench.patterns.oc_perf_sojourn.kuzu
import ocpm_bench.patterns.oc_perf_sojourn.linked_ocel
import ocpm_bench.patterns.oc_perf_sojourn.neo4j_strong
import ocpm_bench.patterns.oc_perf_sojourn.pandas
import ocpm_bench.patterns.oc_perf_sojourn.polars

# Pattern: oc_perf_sync (P3 / Sync)
import ocpm_bench.patterns.oc_perf_sync
import ocpm_bench.patterns.oc_perf_sync._sql
import ocpm_bench.patterns.oc_perf_sync.kuzu
import ocpm_bench.patterns.oc_perf_sync.linked_ocel
import ocpm_bench.patterns.oc_perf_sync.neo4j_strong
import ocpm_bench.patterns.oc_perf_sync.pandas
import ocpm_bench.patterns.oc_perf_sync.polars

# Pattern: ocpq
import ocpm_bench.patterns.ocpq
import ocpm_bench.patterns.ocpq._sql
import ocpm_bench.patterns.ocpq.kuzu
import ocpm_bench.patterns.ocpq.linked_ocel
import ocpm_bench.patterns.ocpq.neo4j_strong
import ocpm_bench.patterns.ocpq.pandas
import ocpm_bench.patterns.ocpq.polars

# Pattern: variants
import ocpm_bench.patterns.variants
import ocpm_bench.patterns.variants._sql
import ocpm_bench.patterns.variants._sql_strong_rels
import ocpm_bench.patterns.variants.kuzu
import ocpm_bench.patterns.variants.linked_ocel
import ocpm_bench.patterns.variants.neo4j_strong
import ocpm_bench.patterns.variants.pandas
import ocpm_bench.patterns.variants.polars

# Pattern: variants_prim
import ocpm_bench.patterns.variants_prim
