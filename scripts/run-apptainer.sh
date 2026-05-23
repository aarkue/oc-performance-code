#!/bin/bash
# sbatch scripts/run-apptainer.sh [config.yaml]
# bash   scripts/run-apptainer.sh [config.yaml]
#
#SBATCH --job-name=ocpm-bench
#SBATCH --partition=c23ms
#SBATCH --constraint=spr8468
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --hint=nomultithread
#SBATCH --time=08:00:00
#SBATCH --output=ocpm-bench-%j.log

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

CONFIG="${1:-dfg-small.yaml}"
SIF="${SIF:-$REPO_DIR/ocpm-bench.sif}"
N_THREADS="${N_THREADS:-16}"

PROJECT_DIR="${PROJECT_DIR:-$REPO_DIR}"
CACHE_DIR="${CACHE_DIR:-$PROJECT_DIR/cache}"
JOB_TAG="${SLURM_JOB_ID:-$(date +%s)}"
OUT_DIR="$PROJECT_DIR/results-$JOB_TAG"
RUN_DIR="/tmp/run-$JOB_TAG"

# Per-job private cache: DuckDB/Kuzu take exclusive file locks, so concurrent
# jobs sharing CACHE_DIR collide. Each job gets its own copy on /tmp; new
# payloads sync back under flock for later jobs.
JOB_CACHE="$RUN_DIR/cache"

[[ -f "$SIF" ]] || { echo "SIF not found: $SIF" >&2; exit 2; }
mkdir -p "$RUN_DIR"/{neo4j-data,neo4j-import,results} "$OUT_DIR" "$CACHE_DIR" "$JOB_CACHE"

if compgen -G "$CACHE_DIR/*" > /dev/null; then
  echo "[run-apptainer] seeding job cache from $CACHE_DIR"
  cp -a --reflink=auto "$CACHE_DIR/." "$JOB_CACHE/"
fi

_sync_results() {
  cp -r "$RUN_DIR/results/." "$OUT_DIR/" 2>/dev/null || true
}

_sync_cache_back() {
  [[ -d "$JOB_CACHE" ]] || return 0
  ( flock -x 9 && cp -an "$JOB_CACHE/." "$CACHE_DIR/" 2>/dev/null || true ) \
    9> "$CACHE_DIR/.sync.lock"
}

trap '_sync_results; _sync_cache_back' EXIT

{
  echo "host=$(hostname) job=$JOB_TAG config=$CONFIG threads=$N_THREADS"
  echo "sif=$SIF sha256=$(sha256sum "$SIF" | cut -d' ' -f1)"
  lscpu | grep -E "Model name|Socket|Core|MHz|NUMA"
  numactl --hardware | head -10
  free -h
  uname -a
} > "$OUT_DIR/env.txt"

# CPU + NUMA pinning. Two regimes:
#  * Exclusive node (paper-grade): cgroup has all cores; slice to the
#    first N_THREADS cores (NUMA node 0) and bind memory to node 0.
#  * Shared node (--cpus-per-task=N): cgroup already capped; use whichever
#    cores SLURM assigned and let memory bind locally.
ALLOWED_CPUS=$(awk '/Cpus_allowed_list:/{print $2}' /proc/self/status)
N_ALLOWED=$(awk -F, '{n=0; for(i=1;i<=NF;i++){split($i,a,"-"); n+=(length(a)==2 ? a[2]-a[1]+1 : 1)} print n}' <<< "$ALLOWED_CPUS")
if (( N_ALLOWED > N_THREADS )); then
  TASKSET_CPUS="0-$((N_THREADS - 1))"
  NUMA_FLAGS=(--membind=0)
else
  TASKSET_CPUS="$ALLOWED_CPUS"
  NUMA_FLAGS=(--localalloc)
fi
echo "[run-apptainer] pinning cpus=$TASKSET_CPUS numa=${NUMA_FLAGS[*]}"

taskset -c "$TASKSET_CPUS" \
  numactl "${NUMA_FLAGS[@]}" \
  apptainer run --cleanenv --writable-tmpfs \
    --env NEO4J_server_memory_heap_max__size=8G \
    --bind "$RUN_DIR/neo4j-data:/data" \
    --bind "$RUN_DIR/neo4j-import:/var/lib/neo4j/import" \
    --bind "$RUN_DIR/results:/app/results" \
    --bind "$JOB_CACHE:/app/cache" \
    "$SIF" matrix --prepare --spec "configs/$CONFIG"

echo "results: $OUT_DIR"
