# Windows NVIDIA 8GB inference setup

Target profile, not measured certification. Need Python 3.11+, recent NVIDIA driver, enough system RAM for OS + overflow, ~4GB free storage for4B GGUF plus runtime (9B needs ~7GB). 4B Q4_K_M is2.74GB, optional9B is5.68GB; memory includes weights, context cache and work buffers, so 8GB does not guarantee full GPU fit. Keep one slot and8192 context for4B; for9B start at4096. Reduce GPU layers or context if OOM. Partial CPU offload trades speed for fit. Close other GPU apps.

1. Create `.venv` and install requirements (README).
2. Obtain recent Windows CUDA llama.cpp release from [official releases](https://github.com/ggml-org/llama.cpp/releases), extract locally and add directory to PATH. Check `llama-server.exe --version` and `--help`; Qwen3.5 needs a supporting build. Record exact release/hash in your hardware report.
3. Download a single text GGUF Q4_K_M from [Unsloth's Qwen3.5-4B conversion](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main) (community quantization of [official Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)). No mmproj needed for this text-only MVP. Verify filename/license/checksum; keep in `models/` (ignored).

Explicit download command (4B download and checksum verification were run on the current Intel Arc device):
```powershell
python -m pip install huggingface_hub
hf download unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf --local-dir models
Get-FileHash models/Qwen3.5-4B-Q4_K_M.gguf
./scripts/start_qwen_windows.ps1 -ModelPath ./models/Qwen3.5-4B-Q4_K_M.gguf
```

4. In another terminal `./scripts/start_backend.ps1 -Mode qwen`. Verify UI says QWEN; transport errors remain errors. Input limits are shown in the UI. The client detects the actual server context and packs history/excerpts within it; use8192 for4B. If protected core alone exceeds the limit, reduce supplied evidence to relevant excerpts. Run context/quality tests with measured hardware before adoption.
5. `python scripts/check_environment.py`; record nvidia-smi peak memory while running, server build, model SHA256, JSON error rate, tokens/s and full-session latency. Calibration requires real annotated interviews.

Flags/API basis: [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), checked 2026-10-02. Availability and memory are not measured on your NVIDIA card in this build.

Fast model: Qwen3.5-4B Q4_K_M, 2.74GB, checksum 00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4. Use CONTEXT_SIZE=8192/server -c8192 and one slot; UI reads actual model filename. This Windows Intel Arc run does not certify NVIDIA or Mac performance. Keep9B as optional quality candidate; evaluate on human Gold before quality claims.
