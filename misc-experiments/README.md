# Misc Experiments

## Alternative Workload Formulations
See [formulations.md](./formulations.md) for the engine-workload formulations
that were tried and discarded in favor of the ones the benchmark reports.

## Neo4j: Directly-Follows Index
See [neo4j_df_index.md](./neo4j_df_index.md) for the effect of a
relationship-property index on the materialized directly-follows edge
(speeds `DFG` by over 3x, omitted for parity with Kuzu and the reference EKG).

## Kuzu: Disk vs. In-Memory
See [kuzu_mem_vs_disk.py](./kuzu_mem_vs_disk.py) for the code.

The scripts times the same workload (weighted DFG) in two database modes: on-disk (i.e., connecting to a `.kuzu` file) and in-memory (i.e., connceting to `:memory:`).
The workload is executed $N=10$ warm times (+ $1$ initial cold run).



Results indicate that on-disk is not slower than in-memory. 
In fact, it seems like on-disk is slightly faster (at least on this workload).

Raw results (single run with $N=10$):
```
on-disk    min= 271.83 ms  median= 297.45 ms
in-memory  min= 331.36 ms  median= 345.59 ms
```