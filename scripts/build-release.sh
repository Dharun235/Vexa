#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.uv-python"
uv sync --locked --extra playground
uv run --locked pytest
uv run --locked ruff check src tests scripts
(cd frontend && npm ci && npm run build)
mkdir -p src/vexa/web
cp -R frontend/dist/. src/vexa/web/
uv build --no-sources
