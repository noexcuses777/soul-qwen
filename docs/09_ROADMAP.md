# Roadmap and gates

2026-10-04 current override: [v5 continuous-chat contract](15_CONTINUOUS_CHAT_REVISION.md) supersedes v1–v4 display/start/follow-up/closure rules below. Name + segment only; selection → same normal composer; all-selected contribution/grounded peer comparison, default 2×n and maximum 3×n public turns per message; optional revision-bound report snapshot, continued chat and no automatic report per message. Earlier fixed v2/A–D and automatic v3 remain compatibility/evaluation paths. Historical measurements are not v5 validation.

1. Freeze docs/source review; implement mock local app and evidence metadata. Gate: all automated tests and saved E2E artifacts.
2. Run Qwen3.5-9B Q4 locally on Windows NVIDIA 8GB and M4 16GB. Record exact model checksum, llama.cpp build, peak memory, latency, JSON failure rate and transcript quality. Adjust context/layers; do not claim device verification before measurement.
3. Collect consented pilot data (30 ideas, 3-5 interviews each), human Gold and annotations. Run A-D with shared budgets and held-out IDs. Gate: blind human assessment and calibration, source-disjoint evaluation.
4. Institution PoC: observe target diversity, repeat use, report use in real interviews/design changes (Persona Studio p.8). Investigate procurement, budget owner and license form (p.9). No paid commitments inferred from simulated personas.
5. Only after measured prompt failures, prepare behavioral SFT/preference tuning on separate NVIDIA/cloud GPU. 9B QLoRA is not assumed feasible on 8GB Windows. Compare heldout PSV-9, false insight rates, latency before adoption.
6. Later: authenticated institution access, source ingestion/RAG, billing, wider pilot. Dynamic routing or EvalOps only after measured need. Every release updates source review, requirements matrix and STATUS.

Revision4 implemented scope: names/profile/three display choices, Qwen conditional rules, user-controlled opening and closure, recommendation cache, typed thread ledger and atomic human evaluation. Deferred NSona dynamic graph/MCP/reddit/product image/caption/visual rubric and training are explicit in docs/14; they require new product evidence/vision evaluation, not a claimed completed text MVP feature.
