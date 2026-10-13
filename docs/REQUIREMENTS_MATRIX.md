# 30 requested items → deliverables

| # | Artifact / verification |
|---|---|
|1|SOURCE_REVIEW.md; both unchanged PDFs + checksum manifest; 11/67 pages reviewed|
|2|01_PRODUCT_SPEC through09_ROADMAP, frozen before implementation|
|3|product spec + API user selection + orchestrator + calibration endpoint|
|4|schemas.Core/PersonaCard/SessionState; eight logical blocks, UNKNOWN constraints|
|5|04_PSV9_EVALUATION five levels for all nine axes; eval.schema|
|6|prompts.ROUNDS; orchestrator; 1/2/3-person tests (12/12/18 group)|
|7|orchestrator.TurnController score/fairness; explicit state_history|
|8|EvidenceLevel, Insight hypothesis + confidence + source level; UI labels|
|9|real Git repo: backend/frontend/eval/training/docs; initial design commit|
|10|Qwen3.5-9B verified model card; local scripts/hardware docs; no large download|
|11|services, context, orchestrator, llm, schemas, app modules|
|12|parse_idea deterministic conservative preservation + missing value tests|
|13|Target fields, relevance+contrast ranking, distinct exposure/role profiles|
|14|build_card with separate validate call; local checks; max2 rebuilds; failure tests|
|15|prompts.agent honesty/independence/conditional reasoning/purchase restraint|
|16|PersonaAgent owned context/state; separate public buffer; recent8 + summary1600; hash test|
|17|eight sections; reference/hypothesis gates; mock full report artifact|
|18|API samples, OpenAPI, env, requirements, pyproject, README, scripts, tests|
|19|eval.run_eval JSONL candidates→judge→CSV/JSON summary; saved smoke outputs|
|20|EvalCase human Gold + rationale; single/three judges, majority and remapped swap|
|21|eval.experiment A/B/C/D same model/idea/topics/seeds/output ceiling; isolation tests|
|22|eval.metrics + analyze_experiment all requested metrics, paired bootstrap; real annotation template|
|23|synthetic labels; mock scores N/A; no human efficacy claims|
|24|training.schema, examples, prepare export, QLoRA scaffold; no training performed|
|25|training.README and hardware docs separate inference/training premise|
|26|unit/integration/HTTP contract/smoke/browser tests; evidence in STATUS|
|27|LLM_MODE mock full flow demonstrated via API and browser|
|28|README Windows/Mac/mock/Qwen/frontend/eval/future tuning exact commands|
|29|STATUS separates completed, executed, unverified, next actions|
|30|repo + ZIP, executable commands, example outputs and screenshot|

Hardware inference and actual human performance are deliberately marked unverified, not omitted from scope. Model download conditional requirement satisfied by scripts/docs and environment check. 실제 Qwen 4B/9B 실행 증거는 examples/에 보존한다. 이는 실행 호환성 검증이며 human 품질/시장 성능 검증과 구분한다.


## 이름·사용자 진행 라운지 추가 요청

| 요청 | 구현/근거 |
|---|---|
| 이름 + 3종 세부 표시 | Presentation/NameEdit, names API, 프로필/표시 select; docs/13 |
| 직접·자동·추천 비교 후 시작 흐름 선택 | 기본 guided WAITING + Qwen 질문6개, 선택 가능한 moderated v3 |
| 유연한 상호작용/종료 | thread/reply/recipient/repair, max4/질문, 사용자 finish, pre-closing/private post |
| 전체 NSona 및 제시한 문헌 | docs/14 전 페이지 범위와 원본9축 crosswalk, 문헌별 적용/한계 |
| 깊은 동기·논리 | Qwen reasoning rules, L2+ timeline quote, separate hypothesis/UNKNOWN validation |
| 자동/실제 평가 | 구조 점검 + 원자 주석 schema, human E조건/표시 실험 계획; 아직 실증은 미실시 |
