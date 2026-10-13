# Work → Codex 인계의 실제 동작

ChatGPT Work와 Codex는 데스크톱 앱 안에서도 별도 화면과 별도 대화 기록을 사용한다. 기존 Work 대화를 실행 중에 Codex 대화로 변환하는 자동 전환은 이 저장소가 제어할 수 없다. Work에서 설계를 만든 뒤 Codex에서 같은 로컬 폴더를 열고 source-of-truth 문서를 기준으로 구현하는 것이 재현 가능한 인계 방식이다. 이 구분은 [OpenAI Learn의 ChatGPT 사용 안내](https://learn.chatgpt.com/docs/use-chatgpt)와 [Codex 환경 안내](https://learn.chatgpt.com/docs/environments/modes)를 기준으로 확인했다.

이 프로젝트에서는 이미 그 인계를 마쳤다.

1. Work 역할: 업로드된 두 PDF를 검토하고 `docs/01`~`09`, `SOURCE_REVIEW.md`, `REQUIREMENTS_MATRIX.md`를 먼저 고정했다.
2. Codex 역할: 이 Git 저장소, FastAPI/UI/eval/training scaffold와 테스트를 만들었다.
3. 현재 Codex 작업: 실제 Qwen3.5-9B GGUF를 llama.cpp로 구동하고 `examples/qwen_*` 실행 증거를 남긴다.

새 Codex 대화에서 이어야 할 때는 이 폴더를 로컬 프로젝트로 열고 다음 문장을 사용한다.

> `docs/01_PRODUCT_SPEC.md`부터 `docs/10_WORK_CODEX_HANDOFF.md`까지를 source of truth로 사용하라. `STATUS.md`의 실제 실행 검증 상태를 먼저 확인하고, mock 결과를 Qwen 실추론 결과로 간주하지 말라. 변경 후 unit test, `scripts/qwen_smoke.py`, 브라우저 전체 흐름을 검증하고 `examples/qwen_verification.json`을 갱신하라.

인계 완료 여부는 말로 선언하지 않는다. 다음 파일이 있어야 완료로 본다.

- `examples/qwen_stage_1_targets.json`: Qwen이 생성한 타깃 가설
- `examples/qwen_stage_2_personas.json`: Qwen이 생성하고 별도 validator가 통과시킨 3개 Persona Card
- `examples/qwen_e2e_result.json`: private → group → private 24개 발화와 8개 섹션 리포트
- `examples/qwen_verification.json`: 모델/서버 버전, 체크섬, 지연시간, 토큰 사용량
