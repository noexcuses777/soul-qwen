# MacBook Pro M4 16GB inference setup

Target profile, not measured certification. Memory is shared with macOS and other apps. Use one Q4_K_M model, text only, one slot, context8192 for4B (4096 optional for9B). Keep multiple GB free for OS. Do not load three models.

```bash
brew install python llama.cpp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m pip install huggingface_hub
hf download unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf --local-dir models
shasum -a 256 models/Qwen3.5-4B-Q4_K_M.gguf
bash scripts/start_qwen_mac.sh "$PWD/models/Qwen3.5-4B-Q4_K_M.gguf"
```

Second terminal from repo, activate `.venv`, then `bash scripts/start_backend.sh qwen`. Open http://127.0.0.1:8000. Metal is used by supported llama.cpp builds; check startup GPU logs. If installed build lacks Qwen3.5 support, build recent [official llama.cpp](https://github.com/ggml-org/llama.cpp) with CMake Metal enabled, set LLAMA_SERVER to that binary. On pressure reduce GPU_LAYERS/CONTEXT_SIZE, match `.env` context; close other apps. Do not claim native 262k model context is practical on this device.

Runtime references: [official model](https://huggingface.co/Qwen/Qwen3.5-4B), [GGUF converter](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main), [server flags](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), checked 2026-10-02. Record model checksum, llama.cpp version, peak unified memory, latency and semantic evaluation. Neither Mac inference nor training was run here. Training is a separate GPU workflow.

Fast model: Qwen3.5-4B Q4_K_M, 2.74GB, checksum 00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4. Use CONTEXT_SIZE=8192/server -c8192 and one slot; UI reads actual model filename. This Windows Intel Arc run does not certify NVIDIA or Mac performance. Keep9B as optional quality candidate; evaluate on human Gold before quality claims.
