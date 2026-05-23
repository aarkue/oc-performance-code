# Minimal benchmark image for ocpm-bench.
#
# Base: official uv image on python 3.14 (matches .python-version and the
# cpython-314 ABI required by the r4pm wheel).
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    BROWSER_PATH=/usr/bin/chromium

WORKDIR /app

# System Chrome for kaleido v1 (used by scripts/plot_results.py for PNG/PDF
# export). Without it plot export fails with ChromeNotFoundError.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium \
 && rm -rf /var/lib/apt/lists/*

# Layer 1: dependency install (cacheable; only re-runs when pyproject/uv.lock change).
# r4pm prerelease pin bundles OCPQ support; edit the version here to swap builds.
COPY pyproject.toml uv.lock ./
COPY ocpm_bench ./ocpm_bench
RUN uv venv "$UV_PROJECT_ENVIRONMENT" --python 3.14 \
 && uv pip install -e ".[dev]" \
 && uv pip install --prerelease=allow "r4pm[polars]==0.5.5a3"

# Layer 2: project assets (changes more often, kept separate from heavy install layer).
COPY configs ./configs
COPY scripts ./scripts
COPY data ./data
COPY README.md ./

# Results and cache directories live as volumes; create them so a fresh
# container without bind-mounts still works.
RUN mkdir -p /app/results /app/cache
VOLUME ["/app/results", "/app/cache"]

ENTRYPOINT ["ocpm-bench"]
CMD ["--help"]
