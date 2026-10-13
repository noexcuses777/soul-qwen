#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export LLM_MODE="${1:-mock}"
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
