#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.uv-python"
export YOLO_CONFIG_DIR="$PWD/.uv-cache/yolo"
export MPLCONFIGDIR="$PWD/.uv-cache/matplotlib"
uv run --isolated --only-group export python scripts/export_model.py
uv sync --locked --extra playground
uv run --locked vexa model install models/yolo11n.onnx
