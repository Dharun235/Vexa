#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.uv-python"
if [ ! -f src/vexa/data/yolo11n.onnx ]; then ./scripts/setup-model.sh; fi
uv sync --locked
uv run --locked pytest
uv run --locked ruff check src tests scripts
uv build --no-sources
