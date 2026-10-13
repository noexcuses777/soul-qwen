# Fine-tuning preparation only

MVP does not fine-tune. Inference uses local GGUF; training later requires a separate compatible NVIDIA/cloud GPU. Do not assume 9B QLoRA is feasible on 8GB Windows or M4 16GB. No training dependencies or weights installed here.

Behavior goals: card adherence, no hallucinated personal experience, natural concise speech, grounded disagreement, conditional agreement, no purchase-intent overclaim. SFT schema pairs card/context with expert response. Preference chosen/rejected focuses on grounded independence vs sycophancy and arbitrary opposition.

```shell
python -m training.prepare --kind sft --source training/data/sft_demo.jsonl --out training/prepared/sft.jsonl
python -m training.prepare --kind preference --source training/data/preference_demo.jsonl --out training/prepared/preference.jsonl
```

Both inputs are synthetic format examples, not sufficient learning data. Collect permissioned expert annotations; split by customer/source/idea; freeze heldout eval first. Export checks heldout source overlap and train/validation leakage. Later training scaffold config is `qlora.example.json`; a future trainer must map it to the chosen pinned training library, use Qwen Transformers weights rather than GGUF, run SFT then preference optimization, and compare holdout PSV-9 + real calibration. No default trainer invocation is provided because training is explicitly out of scope.
