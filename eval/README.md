# PSV-9 and A-D evaluation

Synthetic demo contains three cards and no human Gold; mock judge returns N/A for all nine axes. Its latency is software overhead only. No result here is a Qwen accuracy estimate.

```shell
python -m eval.run_eval --mode mock --out eval/runs/demo
python -m eval.run_eval --mode qwen --dataset eval/data/your_human_holdout.jsonl --judges 1 --out eval/runs/qwen
python -m eval.run_eval --mode qwen --dataset eval/data/your_human_holdout.jsonl --judges 3 --swap --out eval/runs/high_confidence
python -m eval.run_eval --dataset eval/data/your_human_holdout.jsonl --mode qwen --candidates eval/runs/qwen/candidates.jsonl --out eval/runs/rejudge
python -m eval.experiment --mode mock --budget 6000 --seeds 42,43,44
```

Run qwen with a supporting llama.cpp server (README). Judging full history + rubric may require 8192 context with matching server setting; this hardware profile is unverified. Use a separate judge endpoint/model only after explicit configuration changes; default is same local model. Independent judge calls share biases and are not independent human raters. Three judges use majority criterion score, median fallback flagged when no majority. Pair comparison uses true A/B plus swapped B/A and remaps votes. `--swap` is skipped when no human Gold exists; synthetic smoke tests test remapping using a deliberately biased fixture.

EvalCase schema in `schema.py`; each JSONL row includes case ID, dataset_kind, source_split, source IDs, idea, card, question/history, nullable human Gold, origin, optional annotations. Preserve heldout source/customer IDs; Gold must be human authored and permissioned. To assess cross-turn consistency or independence include adequate pre/group/post history; otherwise null. Outputs: candidates.jsonl → judge_scores.jsonl → scores.csv + summary.json. Stored candidates can be rejudged without regenerating.

A-D generator uses eight topic prompts for A/B (private summary questions + six rounds) and 24 calls for C/D, with the SAME completion ceiling (default6000) and same seeds/model/idea/question topics. C agents never see each other. D uses the product protocol and heuristic turn controller. Each condition has per-call cap; JSON repair disabled to preserve ceiling. D report generation excluded from dialogue completion ceiling; total usage includes it separately. Preparing cards is shared across conditions. Input tokens and total usage are reported, so equal output budget must not be described as equal total compute. Mock reserves caps but cannot measure tokenization. Truncated real output fails instead of quietly changing budget.

## Human annotation and comparison
Copy `examples/human_annotation_template.json`, code transcript themes using canonical IDs and add one JSONL row per case/condition/seed:

```json
{"case_id":"idea","condition":"D","seed":42,"annotations":{"dataset_kind":"human","predicted_themes":["time"],"real_themes":["time","trust"],"supported_ids":["time"],"valid_ids":["time"]}}
```

This is a format illustration, not supplied human evidence. `real_themes` null means unavailable. Empty known set has undefined recall (null). Unsupported means uncorroborated in supplied interviews, not proven false. False needs explicit human contradiction annotation. Confidence observations use actual coded outcomes, not imagined purchase probabilities. Founder usefulness 1-5 is supplied by founder after blind report review. Conformity is human-labelled unjustified majority adoption.

```shell
python -m eval.calibrate examples/calibration_synthetic.json --out eval/runs/calibration.json
python -m eval.analyze_experiment --runs eval/runs/experiment.jsonl --annotations eval/data/annotations.jsonl --out eval/runs/analysis --price-per-million 0
```

Analyser outputs CSV for all requested metrics, D-minus-A/B/C paired differences and idea-level bootstrap intervals (seeds averaged within idea). Fewer than two paired ideas gives no CI. Price argument is an accounting estimate per million total generation tokens, not actual electricity cost; local hardware cost must be measured separately. Missing annotations remain unavailable. Cost and latency never establish research quality by themselves.


## v4 대화 구조·원자 단위 진단

```shell
python -m eval.conversation_metrics examples/qwen_guided_release/session.json --out examples/lounge_structure.json
python -m eval.persona_atoms eval/data/synthetic_atoms.json --out examples/atomic_demo_metrics.json
```

전자는 답글/스레드 ID 유효성·화자 분포·미해결 항목을 확인하는 실행 진단이다. 후자는 사람이 문장을 fact/hypothesis/unknown으로 분리하고 support/근거/모순을 주석한 자료만 집계한다. sample은 synthetic이며 근거 없는 수치로 persona 품질을 증명하지 않는다. Spotting Out-of-Character 연구의 원자 단위 평가 관점을 적용했으나 published ACCatom/ICatom/RCatom 구현이라고 부르지 않는다. 질문 추천/표시 3가지의 사용성 비교와 새 v4 E조건은 docs/07,13의 계획이며 아직 수행되지 않았다.
