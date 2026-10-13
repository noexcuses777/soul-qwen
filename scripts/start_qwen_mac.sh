#!/usr/bin/env bash
set -euo pipefail
model="${1:?Usage: bash scripts/start_qwen_mac.sh /absolute/model.gguf}"
case "$(basename "$model" | tr '[:upper:]' '[:lower:]')" in
  *qwen*.gguf) ;;
  *) echo 'Select the existing Qwen GGUF model explicitly.'; exit 1 ;;
esac
test -f "$model"
exec "${LLAMA_SERVER:-llama-server}" -m "$model" --alias persona-qwen --host 127.0.0.1 --port 8080 -c "${CONTEXT_SIZE:-8192}" -np 1 -ngl "${GPU_LAYERS:-99}" -b 256 -ub 128 --jinja --reasoning off --chat-template-kwargs '{"enable_thinking":false}'
