# 2026-10-02 설계 보완 — 구현 기준

원본 두 PDF와 공유 가이드 https://chatgpt.com/share/6abf3cd9-b4dc-83ee-b127-62974e9acd7f 전체를 재검토했다. 기존 01–09 문서의 기본 원칙을 유지하며 충돌 시 이 문서가 최신 구현 기준이다.

## 입력과 문맥

Q1 200자, Q2 1000자, Q3-1 1500자, Q3-2 600자, Q4-1 1000자. Q3/Q4는 제목이다. 근거 최대8개, 각1500자, 총6000자. UI 카운터와 API가 동일한 정책을 쓴다. 한도는 Unicode code point 기준. 기존 저장 세션은 읽을 수 있게 보존한다. 타깃 편집 각300자, 추가 질문500자. 자료 원문은 저장하며 모델에 주제 관련 발췌를 전달한다. 발췌는 원문 offset/ID를 보존하고, 누락된 자료를 UNKNOWN 또는 미관측으로 취급한다.

4B Q4_K_M을 빠른 기본 선택으로 제공하며 9B 실행도 유지한다. shared model 1개, context8192, parallel1. 서버가 알려주는 실제 slot 문맥 이하로 클라이언트 예산을 제한한다. 카드·근거·현재 질문은 보호하고 중복 brief 필드, 초기 state 중복, 빈 기본값을 제거한다. 최근6개 public/4개 own + 귀속된 older summary를 유지하고 실제 tokenizer로 예산을 확인한다. 부족하면 오래된 가시 turn을 summary로 이동하고 발췌 길이를 줄인다. 보호된 필수정보까지 넘으면 명확한 입력 오류를 낸다. transport/503은 한 번 재시도, JSON/schema 오류도 한 번 복구한다. 대화가 실패하면 저장된 완료 turn 이후부터 재개한다.

## 대화의 조직

Private pre 각1회 → 여섯 그룹 라운드 → Private post 각1회. 기존 실험 A–D의 호출수/토큰 예산 비교를 보존하기 위해 기본 그룹은 3명일 때18회, 전체24회이다. 1–2명은 그룹12회. Problem Reality와 Solution Reaction에서는 **다른 참여자의 의견을 전달하지 않는다**. Cross-reaction부터 공개 발화만 전달하고 다른 참여자의 pre/post는 전달하지 않는다.

Moderator는 Cross/Conflict에서 실제 공개 발화 ID·내용을 지목한다. 인접쌍 question→nominated answer를 끼어들기 없이 처리하고, 뒤이어 해당 조건이 다른 참여자를 선정한다. 명시적 nominee 우선, 없으면 relevance + disagreement + direct mention + unresolved − recency score. 점수·선택 이유·질문·reply target을 turn metadata에 기록한다. 입장 차이가 없는 경우 조건 확인을 묻고 반대를 만들지 않는다. 답변은 2–3문장, 기본240 output tokens. stance 변화에는 자신의 이유가 필요하며 post에서 초기/최종 입장과 변화 이유를 비교한다. 창업자 추가 질문은 별도 라운드/로그로 최대2명에게 질문하고 표준 실험의24회와 분리한다.

발화 경계는 완성된 응답 단위이다. UI는 저장된 진행상황을2초 간격으로 읽고 발화를 즉시 표시한다. 다음 모델 호출은 앞선 응답이 끝나면 시작한다. 인위적인 대기시간을 삽입하지 않는다. 모델 생성 지연을 인간의 망설임/동의 강도/현실적인 대화텀으로 해석하지 않는다.

## 원문/연구 → 설계 (적용은 공학적 추론이며 효능 입증이 아니다)

| 근거 | 설계 반영 |
|---|---|
|NSona 원본 slides34–35 Who/What/How|identity, problem/decision/experience, interaction style; 근거 없는 신상/경험 UNKNOWN|
|NSona slides36–38 turn-taking, adjacency, reply prediction, summary buffer|명시적 nominee와 귀속 reply ID, protected question-answer sequence, owned/public summary 분리; dynamic LLM graph는 MVP 제외|
|Sacks, Schegloff & Jefferson1974 [원문](https://pure.mpg.de/pubman/item/item_2376846_3/component/file_2376845/Sacks_1974_simplest_systematics.pdf)|현재 질문의 지목 우선, 발화 경계에서 순서 결정; 3인 모두 동일한 질문을 매번 자동 합창시키지 않도록 실제 발화에 연결한 후속질문|
|Schegloff, Jefferson & Sacks1977 [저자 출판물 아카이브](https://www.conversationanalysis.org/schegloff-publication-archive/)|repair: 다른 사람 경험을 대신 수정하지 않고 자신의 불명확한 조건·입장 변화 이유를 명시하도록 prompt|
|Stivers et al2009 [원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC2705608/)|인간의 gap/overlap 조직은 참고하되 LLM latency를 그 현상으로 가장하지 않음; 순차 공개, 중복 출력 없음|
|Baltaji et al2024 [논문](https://aclanthology.org/2024.c3nlp-1.2/)|persona conformity/impersonation 위험: 초반 독립 응답, private post, 타인의 경험 전용 금지, PSV9/Conformity 평가|
|Wang et al2024 [논문](https://aclanthology.org/2024.acl-long.331/)|다중대화의 우월성을 전제하지 않고 동일 모델·예산의 A–D 실험 유지|

## 공유 가이드 전체 대응 / 실행 경계

| 가이드 내용 | 파일/변경 |
|---|---|
|제품 포지셔닝, NSona 채택/수정/제외, 입력·추천·선택·검사·인터뷰·리포트·실제보정|01_PRODUCT_SPEC, SOURCE_REVIEW, REQUIREMENTS_MATRIX, app/services/frontend|
|Who/What/How 확장 8개 구조, 중요한 구매조건, UNKNOWN, immutable/session 분리|02_PERSONA_SCHEMA, schemas/context; 세부 선택 필드 확장, 근거 없는 값 기본 UNKNOWN|
|6–8 타깃 추천, exposure/alternative/role 대비, 미리보기 수정|services/prompts/schema; 6개 기본 추천, 검증 후 카드 JSON 수정 API/UI|
|독립 pre/group/post, adjacency, speaker score, 턴 길이·순서·텀, lounge 추가질문|03_DIALOGUE_PROTOCOL + 이 문서, orchestrator/context, ask API/UI, turn metadata|
|9개 평가 rubric, human Gold, 1/3 judge, majority/order swap|04_PSV9_EVALUATION, eval/run_eval/schemas/data|
|근거 L0–4, 데이터 schema, 검색/관련근거 선택|05_DATA_SCHEMA, services evidence window selection, 전체 원문 SQLite 저장|
|역할별 structured prompts, JSON/validator, 한 모델 여러 context|06_PROMPT_SPEC, llm/prompts/context|
|generic/single/independent/group A–D, 실제 인터뷰 지표/통계|07_EXPERIMENT_PLAN, eval/experiment/metrics/analyze_experiment|
|로컬 Qwen GGUF, Windows/Mac 실행, backend/frontend/API/저장소|08_ARCHITECTURE, scripts, WINDOWS_8GB, MAC_M4_16GB, README|
|Milestones/비용절감/프롬프트→평가→필요할 때 학습|09_ROADMAP, training scaffold/examples; 실제 학습하지 않음|
|Work 설계 확정→Codex 구현/테스트·handoff|10_WORK_CODEX_HANDOFF; 동일 작업에서 설계 파일을 먼저 고정한 후 구현|

실제 고객/Gold/behavioral dataset 수집, human coding, 시장 검증, fine-tuning은 코드 존재와 실행을 구분한다. 원문에 없는 고객을 생성하거나 human 검증 완료로 표기하지 않는다. mock는 smoke만, 실제 Qwen 실행은 기능 검증이며 사람 대비 품질 입증이 아니다. 원본9B 증거를 보존하고4B 증거를 별도 저장한다.


최종 리포트 grammar는 8개 고정 key, 섹션별1개 insight, 최대180자 및 실제 utterance/source ID enum을 사용한다. 타깃과 agent의 source/reply IDs도 해당 요청에서 존재하는 값으로 제한한다. 로컬 검증은 생성 제약과 별도로 유지한다. 최대 입력 probe는7285/8192, 실제4B는34회(실패리포트 포함)·24발화·8섹션 완료. Gold를 수집하기 전 의미·경험·구매의향에 관한 품질을 검증 완료라고 표현하지 않는다.
