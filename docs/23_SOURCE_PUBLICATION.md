# SOUL source publication — 2026-10-13

- Destination: `noexcuses777/soul-qwen`, private repository.
- PR branch: `codex/soul-qwen-release`, base: `main`.
- Exported current SOUL working-tree source into an independent checkout. No original Git history, other branches, model weights, or other model implementations were copied.
- Included Next.js frontend, FastAPI backend, Qwen prompts/client/context/dialogue/report logic, evaluation pipeline, synthetic fixtures, training preparation, setup scripts, tests and design documentation.
- Preserved the original MIT license and attribution. The Qwen model is obtained separately; this repository distributes no model weights.
- No fine-tuning was performed. `training/` is preparation only, with explicitly synthetic examples.
- `.env.example` contains local configuration only. Private environment files, API keys, conversation databases, logs, private verification output, runtime binaries, dependency/build folders and model checkpoints are excluded.
- Added stricter ignore rules for future training/evaluation data. Source packaging reads Git-visible files and additionally rejects private/runtime/model paths even if accidentally tracked; the package guard has regression tests.
- Current source scan is not a guarantee about arbitrary future files. Inspect staged files before each push and never force-add private assets.
- Previous local verification: backend 237 tests, frontend 86 tests; TypeScript, lint and production build passed. Publication-specific tests and GitHub CI provide further source checks; they do not measure customer validity or general Qwen quality.
