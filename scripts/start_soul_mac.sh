#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$task_root"
export LLM_MODE="${LLM_MODE:-qwen}"
export LLM_BASE_URL=http://127.0.0.1:8080/v1 LLM_MODEL=persona-qwen
export CONTEXT_SIZE="${CONTEXT_SIZE:-8192}"
export SESSION_DB="${SESSION_DB:-$task_root/data/sessions.sqlite3}"
export SOUL_API_ORIGIN=http://127.0.0.1:8001
task_python="${PYTHON:-$task_root/.venv/bin/python}"
test -f .next/BUILD_ID || { echo 'Run npm ci --ignore-scripts and npm run build first.'; exit 1; }
if [ "$LLM_MODE" = qwen ]; then
  "$task_python" -c 'import httpx, os, re; from pathlib import Path; p=httpx.get("http://127.0.0.1:8080/props",timeout=10).json(); name=Path(p.get("model_path", "")).name; assert re.search(r"qwen.*\.gguf$",name,re.I), "Port 8080 must contain the explicitly selected Qwen GGUF"; n=int(p.get("default_generation_settings",{}).get("n_ctx",0)); assert n>=int(os.environ["CONTEXT_SIZE"]), "CONTEXT_SIZE must not exceed the model server context"'
fi
"$task_python" -m uvicorn backend.app:app --host 127.0.0.1 --port 8001 &
task_api=$!
trap 'kill "$task_api" 2>/dev/null || true' EXIT INT TERM
task_ready=false
for task_i in $(seq 1 40); do
  if "$task_python" -c "import httpx; h=httpx.get('http://127.0.0.1:8001/api/health').json(); assert h['status']=='ok' and h['mode']=='$LLM_MODE'" >/dev/null 2>&1; then task_ready=true; break; fi
  kill -0 "$task_api" 2>/dev/null || { echo 'Backend failed to start.'; exit 1; }
  sleep 1
done
"$task_ready" || { echo 'Backend/Qwen connection is not ready. Start the explicit Qwen model server first.'; exit 1; }
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port "${PORT:-8000}"
