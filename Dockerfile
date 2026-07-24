# Minimal benchmark image for ocpm-bench.
# Base pinned by digest: uv python3.14-bookworm-slim; venv uses managed CPython 3.14.5 (SQLite 3.53.1).
FROM ghcr.io/astral-sh/uv@sha256:7cf77f594be8042dab6daa9fe326f90962252268b4f120a7f5dccce4d947e6c1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    BROWSER_PATH=/usr/bin/chromium

WORKDIR /app

# Chromium: kaleido PNG/PDF export in scripts/plot_results.py.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium \
 && rm -rf /var/lib/apt/lists/*

# Dependencies (cached until pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
COPY ocpm_bench ./ocpm_bench
RUN uv python install 3.14.5 \
 && uv venv "$UV_PROJECT_ENVIRONMENT" --python 3.14.5 --python-preference only-managed \
 && uv pip install -e ".[dev]" \
 && uv pip install --prerelease=allow "r4pm[polars]==0.5.5a6"

# Project assets (change more often than the install layer).
COPY configs ./configs
COPY scripts ./scripts
COPY data ./data
COPY README.md ./

# Results/cache mount as volumes; create so a bind-mount-less run still works.
RUN mkdir -p /app/results /app/cache
VOLUME ["/app/results", "/app/cache"]

ENTRYPOINT ["ocpm-bench"]
CMD ["--help"]
