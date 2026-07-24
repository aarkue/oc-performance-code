# Neo4j: Directly-Follows Relationship-Property Index

Effect of a relationship-property index on the materialized `DF` edge in Neo4j.

## Setup

- HPC node (2x Xeon Platinum 8468, 16 cores, 32 GB), Apptainer container.
- Neo4j 5.26.27, 16 GB heap + 16 GB page cache, timestamp index on.
- Toggle `OCPM_NEO4J_DF_INDEX`: `1` creates
  `CREATE INDEX df_entitytype FOR ()-[r:DF]-() ON (r.EntityType)`.
- Mean of N=10 warm reps per cell.

## Result files (`code/results/`)

- `neo4j-cluster.jsonl` -- index OFF (paper baseline).
- `neo4j-cluster-df-idx.jsonl`, `neo4j-cluster-df-idx2.jsonl` -- index ON, two runs.

## Runtime (ms), factor = no-idx / idx

| workload | no-idx | idx1 | idx2 | factor1 | factor2 |
|----------|-------:|-----:|-----:|--------:|--------:|
| dfg      |  888.4 | 236.7| 245.9| **3.75**| **3.61**|
| variants | 1625.0 |1716.9|1726.0|    0.95 |    0.94 |
| ocpq     |  550.2 | 521.5| 567.1|    1.06 |    0.97 |
| ekg      |  445.2 | 377.5| 409.0|    1.18 |    1.09 |
| sync     | 5699.2 |5876.1|5898.5|    0.97 |    0.97 |
| sojourn  | 3836.5 |3964.7|4064.6|    0.97 |    0.94 |
| heatmap  | 1988.0 |1747.1|1813.7|    1.14 |    1.10 |
| conv     |   34.9 |  39.3|  36.3|    0.89 |    0.96 |

Speeds up `DFG` only (~3.6-3.8x), all other workloads flat.

## Why the benchmark omits it

- Kuzu supports primary-key indexes only, cannot define an equivalent (parity).
- Matches reference EKG encodings 
- Workload-specific; the benchmark reports one uniform, untuned configuration.

Magnitude disclosed in the paper (Section 3.4) and the response letter.
