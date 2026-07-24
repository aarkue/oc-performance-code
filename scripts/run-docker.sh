#!/bin/bash
# Full-matrix (or single-config) benchmark run via Docker Compose (counterpart to run-apptainer.sh).
# Usage: bash scripts/run-docker.sh [config.yaml] (default paper-all.yaml).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

CONFIG="${1:-paper-all.yaml}"
N_THREADS="${N_THREADS:-$(nproc)}"
export NEO4J_HEAP="${NEO4J_HEAP:-8G}"
export NEO4J_PAGECACHE="${NEO4J_PAGECACHE:-8G}"

echo "[run-docker] config=$CONFIG threads=$N_THREADS neo4j heap=$NEO4J_HEAP pagecache=$NEO4J_PAGECACHE"

# Rebuild to carry the current code; SKIP_BUILD=1 uses a `docker load`-ed image verbatim.
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  docker compose build bench
fi

# Bring Neo4j up first to surface config errors before the matrix starts.
docker compose up -d neo4j
echo "[run-docker] waiting for Neo4j..."
until docker compose ps neo4j | grep -q healthy; do sleep 3; done

# Effective Neo4j memory, recorded for the paper's setup section.
docker compose exec -T neo4j cypher-shell -u neo4j -p testpassword \
  "SHOW SETTINGS YIELD name, value \
   WHERE name IN ['server.memory.heap.max_size','server.memory.pagecache.size'] \
   RETURN name, value;" || true

docker compose run --rm \
  -e OCPM_THREADS="$N_THREADS" \
  -e RAYON_NUM_THREADS="$N_THREADS" \
  -e POLARS_MAX_THREADS="$N_THREADS" \
  -e OMP_NUM_THREADS="$N_THREADS" \
  -e OPENBLAS_NUM_THREADS="$N_THREADS" \
  -e MKL_NUM_THREADS="$N_THREADS" \
  -e NUMEXPR_NUM_THREADS="$N_THREADS" \
  bench matrix --prepare --spec "configs/$CONFIG"

echo "[run-docker] done. Results under ./results/ (see results_path in configs/$CONFIG)."
