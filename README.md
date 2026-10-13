# SOUL — Qwen 기반 페르소나 인터뷰

저장소: https://github.com/noexcuses777/soul-qwen · 구현 브랜치: `soul-qwen-release`.
현재 실행 모델은 Qwen3.5-4B Q4_K_M이며 추가 fine-tuning을 수행하지 않았다. 가중치, API 키, 실제 대화 DB, 로그, 사용자 자료는 이 저장소에 포함하지 않는다. 원본 프론트엔드의 MIT 고지는 LICENSE에 유지한다.

```shell
git clone --branch soul-qwen-release https://github.com/noexcuses777/soul-qwen.git
cd soul-qwen
```

SOUL의 Next.js 화면과 기존 Persona Studio의 FastAPI/Qwen 기능을 연결했다. 아이디어 → 타깃 추천 → 최대 3인 선택·생성·검사 → 카드 비교 → 자유로운 다중대화 → 출처가 있는 리포트 → 이어 묻기 순서로 사용할 수 있다. 이름 옆에는 이용자 예시만 표시한다.

공개 대화는 전원 독립 답변 뒤 조건 비교·상대 질문·원발화자의 재검토·필요한 조건 탐색으로 이어진다. 3명 기준 6개 고정 흐름을 대신하며 내용에 따라 일찍 반환하거나 최대 15개 발언까지 살펴본다. 자세한 종료/근거 계약은 [대화 깊이](docs/21_DIALOGUE_DEPTH.md)에 있다. 새 추천의 가상 이름은 무작위로 정하고 저장 후 유지한다. 리포트의 내부 L0/u1 표시는 한국어 근거 유형과 이름·발언 순서로 읽을 수 있다.

‘이 쟁점 더 살펴보기’는 원질문을 재포장하지 않는다. 최신 공개 답변·카드 조건·이미 묻거나 제안한 질문을 Qwen이 검토하고, 새 조건을 논의할 수 있을 때만 질문을 채운다. 실제 정확도/유용성 같은 관측이 필요하면 자료 확인 안내를 표시하며 자동으로 가상 대화를 시작하지 않는다. 새 질문이 없으면 추천을 보류한다. [후속 질문 계약](docs/22_FOLLOWUP_RECOMMENDATIONS.md)을 따른다.

생성한 의견은 **AI 시뮬레이션 가설**이다. 실제 고객 인터뷰와 행동 데이터로 검증해야 한다. Qwen은 한 개만 띄우며 카드·불변 Core·개인 문맥·세션 상태를 분리한다. 다른 모델의 가중치·학습·추론 작업은 사용하지 않는다. 이번 통합은 기존 구조화 프롬프트/스키마를 연결한 작업이며 새 fine-tuning을 수행했다는 뜻이 아니다.

아이디어 입력은 화면 순서대로 한 줄 소개·사업 분야/고객 유형·아이디어 설명·문제와 기존 방식의 차이를 적는다. 배경·수익 모델·실현 계획·본인 역량은 펼쳐서 추가한다. 각 칸의 글자 제한은 입력란 아래에 나온다. TXT/MD/CSV 자료는 파일 버튼으로 관련 원문을 추가할 수 있고, PDF는 관련 문장을 원문 발췌에 붙여 넣는다. 파일은 처음에 미검증 L0으로 저장되며 실제 출처에 맞는 근거 수준을 사용자가 선택한다. [화면 재점검 기록](docs/19_FRONTEND_UPDATE.md)에 기준 브랜치와 다른 부분의 이유가 있다.

## Windows 설치·실행

Node.js 20.9 이상, Python 3.11 이상과 Qwen 지원 llama.cpp 서버가 필요하다. 저장소 루트에서 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
npm ci --ignore-scripts
npm run build
Copy-Item .env.example .env
```

이미 보유한 **Qwen GGUF**와 **llama-server.exe**의 실제 경로를 지정한다. 서버 :8080이 실행 중이면 선택한 모델 경로가 일치하는지 확인 후 재사용한다. 다른 모델에 자동 연결하거나 mock으로 전환하지 않는다.

```powershell
.\scripts\start_soul_windows.ps1 -ModelPath C:\models\Qwen3.5-4B-Q4_K_M.gguf -Server C:\llama\llama-server.exe
```

SOUL 화면: http://127.0.0.1:8000 · FastAPI: http://127.0.0.1:8001/docs · Qwen: :8080. 종료하면 이 스크립트가 직접 시작한 backend/model만 종료한다. 이전부터 실행 중인 모델은 그대로 둔다. 이미 :8000이 사용 중이면 기존 런처를 종료하거나 `-Port 3000`으로 새 화면을 확인한다. :8001은 통합 backend 전용이다.

Qwen 9B는 `-ModelPath`를 해당 4-bit GGUF로 바꾼다. 메모리/속도에 따라 4B를 사용할 수 있으며 품질이 같다고 가정하지 않는다. 이 작업의 실제 실행 모델 및 측정은 [STATUS.md](STATUS.md)에 기록한다. Windows NVIDIA 8GB 세부 설정은 [설치 문서](docs/WINDOWS_8GB.md)를 따른다. 모델은 Git에 포함하지 않는다.

## MacBook Pro M4 16GB

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
npm ci --ignore-scripts
npm run build
cp .env.example .env
# 터미널 1: Qwen 지원 llama.cpp 설치 후, 해당 모델만 지정
LLAMA_SERVER=/absolute/path/llama-server bash scripts/start_qwen_mac.sh /absolute/path/Qwen3.5-4B-Q4_K_M.gguf
# 터미널 2
bash scripts/start_soul_mac.sh
```

Metal·메모리 설정은 [Mac 실행 문서](docs/MAC_M4_16GB.md)를 참고한다. 현재 Windows에서 실행한 결과만으로 Mac 성능을 검증했다고 하지 않는다.

## 모델 없이 소프트웨어 실행 점검

명시적인 mock 모드이며 화면에도 합성 결과라는 표시가 나온다. 실제 Qwen/시장 성능 시험과 구분한다.

```powershell
.\scripts\start_soul_windows.ps1 -Mode mock
# 새 합성 아이디어로 전체 경로 확인. 기존 사용자 세션은 재사용/삭제하지 않음
.\.venv\Scripts\python.exe -X utf8 scripts/soul_smoke.py --base-url http://127.0.0.1:8000
```

Mac에서는 `LLM_MODE=mock bash scripts/start_soul_mac.sh`를 사용한다. Qwen 모드의 연결 실패 시 mock 결과로 몰래 대체하지 않는다.

## 개발·검증

```powershell
# 터미널 1 (Qwen 서버는 별도 실행)
$env:LLM_MODE='qwen'
$env:SESSION_DB='data/sessions.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
# 터미널 2
npm run dev -- --hostname 127.0.0.1 --port 8000
```

`SOUL_API_ORIGIN` 기본값은 `http://127.0.0.1:8001`이다. 변경 시 **빌드 전에** 설정하고 다시 빌드한다. `/api/*` 요청은 같은 출처로 프록시하며 긴 로컬 추론에 30분의 연결 제한을 둔다. 화면은 GET 폴링으로 완료된 공개 말풍선을 읽는다. Private Pre/Post는 대화창에 공개하지 않는다. 특정 참여자에게 질문하는 화면도 현재 공개 세션의 일부이며 비공개 DM으로 보장하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
$env:LLM_MODE='mock'
$env:SESSION_DB='verification-private/test-import.sqlite3'
.\.venv\Scripts\python.exe -m pytest -q
node tests/frontend_korean.test.cjs
npm ci --ignore-scripts
node tests/soul_frontend.test.cjs
node tests/chat_presentation.test.cjs
node tests/next_question_frontend.test.cjs
node tests/persona_presentation.test.cjs
node "src/app/(app)/report/report.test.cjs"
npm run typecheck
npm run lint
npm run build
.\.venv\Scripts\python.exe -m eval.run_eval --mode mock --out eval/runs/demo
.\.venv\Scripts\python.exe -X utf8 scripts/soul_smoke.py --out verification-private/smoke.json
```

최종 회귀 검사에서 backend **183개**가 통과했다(159.90초). Node 검사는 기존 한국어 formatter 33개, 프론트 API·세션 경계 19개, 채팅 표시 5개, 이름·선택 연결 5개, 리포트 SSR 10개로 **총 72개**가 통과했다. 전체 TypeScript·ESLint 검사도 통과했으며 production 의존성의 `npm audit` 결과는 0건이다. 개발 의존성의 upstream ESLint 경고 범위는 [STATUS.md](STATUS.md)에 기록한다.

Node 경계 검사는 메모리 내 fetch·저장소·타이머를 사용하며, SSR 검사는 합성 리포트의 인용·입장 표시·저장 날짜·내보내기를 확인한다. 실제 모델이나 고객 성능을 평가하는 검사는 아니다. 같은 명령을 `.github/workflows/qwen-ci.yml`에서 실행하며, TypeScript/React를 사용하는 새 Node 검사는 `npm ci` 이후에 실행한다.

첫 추천과 카드 생성은 실제 모델 작업이다. 기다리는 동안 페이지를 닫더라도 저장된 세션을 복원할 수 있고 대화 실패 시 같은 질문으로 재개한다. 이름/세그먼트 외의 근거 없는 인구통계와 과거 경험을 임의로 채우지 않는다. 입력의 글자 수 제한은 backend와 UI가 공유한다.

## 리포트와 평가·학습 준비

첨부 SOUL PDF/HTML의 배치를 사용하고 숫자·이름·예시 주장은 재사용하지 않았다. 기존 8개 인사이트 + 공개 발화의 쟁점별 의견/조건/인용, 같은 쟁점의 입장 표현 변화, 미확인 사항, 실제 고객 질문을 제시한다. KPI는 세션 배열에서 집계하며 구매확률·PMF·인간 유사 정확도를 산출하지 않는다. 이어 묻기 후 리포트가 오래되었다는 표시와 갱신 기능을 제공한다. JSON/텍스트 저장과 인쇄(PDF 저장), 질문 복사도 지원한다.

`eval/`에 PSV-9 rubric/Gold schema/1 또는 3 judge·A/B swap·A–D 비교·실제 인터뷰 calibration이 있다. 합성 예시는 smoke에만 사용한다. 실제 human Gold와 행동자료가 없어 평가 점수·효과를 주장하지 않는다. [평가 실행](eval/README.md), [실험 계획](docs/07_EXPERIMENT_PLAN.md), [실제 인터뷰 calibration](docs/05_DATA_SCHEMA.md)을 따른다.

`training/`은 SFT/preference 스키마와 자료 준비 scaffold다. 학습을 실행하지 않았다. 향후 허가된 실제 자료 수집 → holdout 분리 → prompt baseline 평가 → 데이터 정제 → 별도 NVIDIA/cloud GPU로 학습 → Qwen baseline과 회귀 비교 순서로 진행한다. 9B QLoRA를 일반 Windows 8GB 추론과 같은 작업으로 취급하지 않는다.

## 구조·보존

`src/` Next.js SOUL 화면 · `backend/` Qwen API/생성/검사/대화/리포트 · `frontend/` 기존 Python 호환용 화면 · `eval/` 평가 · `training/` 학습 준비 · `docs/` 설계 · `tests/` 회귀검증. 최신 화면은 `feat/frontend-update` 기준이다. 후보 이름·아바타·공용 편집·실제 아이디어 요약을 [화면 업데이트 계약](docs/19_FRONTEND_UPDATE.md)에 따라 연결했다. 신규 통합의 source of truth는 [SOUL 통합 계약](docs/18_SOUL_INTEGRATION.md), 세부 기존 설계는 문서 01–17이다.

기존 Persona Studio 저장소·사용자 SQLite는 덮어쓰지 않는다. `data/`, `.env`, 모델, runtime, 사용자 인터뷰 기록과 첨부 원본 PDF는 공개 브랜치에서 제외한다. 문서의 이전 `examples/` 경로는 원래 로컬 저장소의 역사 기록이며 공개된 실행 자료를 뜻하지 않는다. 이번 검증만 [검증 기록](docs/SOUL_VERIFICATION.md)에 남긴다.
