#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.uv-python"
if [ ! -f models/yolo11n.onnx ]; then ./scripts/setup-model.sh; fi
uv sync --locked
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm ci && npm run build)
fi
rm -rf src/vexa/web
mkdir -p src/vexa/web
cp -R frontend/dist/. src/vexa/web/
exec uv run --locked vexa serve --model models/yolo11n.onnx
