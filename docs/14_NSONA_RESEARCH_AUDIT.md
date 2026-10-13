# NSona 전 페이지 검토와 연구→설계 추적표

2026-10-04 변경: 아래 NSona 전체 검토/문헌 결과는 유지한다. 구현 대응의 표시·시작·턴 예산·종료 부분은 [v5 연속 채팅 설계](15_CONTINUOUS_CHAT_REVISION.md)로 갱신됐다. 이전 v4의 max4/역할 표시/pre-closing은 현재 기본 동작이 아니다.

2026-10-03 재업로드 Downloads 파일과 보관 원본의 SHA256이 일치한다: `c4f732afb11ff2d6b7d13a949b26c0ae870734ca954885a4d75cbb4a63ae5e91`. 사용자가 제공한 67쪽 원본을 전체 contact sheet로 확인하고 핵심 생성·대화·평가·문헌 슬라이드를 확대 확인했다. 원본 PDF는 이 공개 브랜치에 배포하지 않는다. 원본 글꼴의 텍스트 추출은 깨지므로 이미지 기준이다. 내용 전체를 검토했다는 것은 NSona의 모든 기능을 이번 MVP에 복제했다는 뜻이 아니다. 이전 요구(로컬 4/9B, 최대 3인, state machine, fine-tuning 준비만)와 충돌하는 것은 아래에 명시한다.

## 페이지별 전 범위 대응

| 페이지 | 원본 내용 | Persona Studio 반영/차이 |
|---|---|---|
| 1–5 | 발표 소개, 연구·설계·개발 협업, 문제 출발 | docs source 보존, 제품/구현/평가 책임과 근거 추적. 발표자 소개는 제품 기능이 아님 |
| 6–11 | 리서치 비용, persona 사용 한계, 일상 협업 AI user | 인터뷰 준비·가설 발견·실제 인터뷰 보정 포지셔닝. 실제 고객의 대체라는 표현 금지 |
| 12 | 구조적인 persona 생성과 편집 | Builder + 별도 Validator + JSON 편집/재검사 + 사람의 타깃 선택 |
| 13 | 특성/발화 제어 | Who/What/How, interaction_style, evidence UNKNOWN, reasoning rule, 프로필 |
| 14 | 최대 3인 라운지 | 하나의 말풍선 대화창, 1–3인 독립 context, reply 관계 |
| 15 | 이미지로 공동 아이데이션 | 현재 사업 인터뷰는 텍스트. 이미지 caption/시각판단 미구현·N/A. 실제 vision model/자료/Gold 확보 후 확장 |
| 16 | 생성→특성 설정→평가→대화 보정→리서치 | API select/validate/open/ask/finish/report/calibrate, immutable/state 분리 |
| 17 | persona 품질 질문 | PSV-9 + decision rule validation + 실응답 수동 검토 |
| 18–19 | 9축/5개 개념군 | 아래 전체 crosswalk. 회고는 근거 있을 때만, 발산은 억지 창작 아닌 조건/대안 가설 |
| 20 | 생성 템플릿/규칙 비교 | typed schema + generation instruction + evidence gate. 원본의 -5.8/+8.7%는 NSona 실험 결과이고 Qwen 성과로 전용하지 않음. 마지막 ‘실험2’ 표기는 슬라이드 원문이며 최종 네 번째 조건으로 해석 |
| 21 | Task/Instruction, 9축 rubric 프롬프트 비교 | prompts task별 분리, 역할/말하기/일관성/맥락/평가 규칙. 원본의 -25.4/-40.7/+18.6%는 재현하지 않은 NSona 결과 |
| 22–23 | 리서처 피드백, 리서치 허브 | 창업자 주도 질문, 추천, 데이터 근거와 hypothesis 표시. 반복 개선. 외부 리서치 커넥터는 미구현 |
| 24–28 | 엔지니어링, 사용자 관점, 다중대화·복잡도·평가 문제 | 한 로컬 모델, shared client, 저장/재개, schema/context guard; 세 문제 각각 구조 테스트 |
| 29–33 | 1:1과 다중대화 차이, 누가/누구에게/언제/무엇 | 화자 ID와 별칭 분리, 수신자 지명, thread/reply, 턴 제어, private 격리 |
| 34–35 | Who-What-How; sociolect/semantic signal/pragmatic act | Identity/상황, 문제·대안·판단 가설, Style/dialogue_act. 나이·성별 기반 말투 고정 금지 |
| 36–37 | turn-taking/adjacency, 이론 및 NLP 문헌 | 아래 10개 논문/저서 매핑. 숨은 chain-of-thought를 저장/노출하는 방식은 쓰지 않고 결정된 act/근거만 기록 |
| 38–39 | inter-turn layer: turn/reply, image caption, summary, 후속추천, 발화요약 | turn/reply/thread, bounded attribution summary, Qwen 질문 추천 + 미해결 칩. caption은 vision 확장 항목 |
| 40–41 | 동적 graph, loosely coupled node/hook, FE/BE/core/chat/UX/MCP/search/data | node 책임을 모듈로 분리. model act가 다음 반응을 제안하지만 허용 action·budget은 명시적 controller. 초기 dynamic graph 금지 요구를 유지. Reddit/product image/MCP/microservice 분산 실행은 보류; 외부 자료를 자동 사실로 만들지 않음 |
| 42–46 | agent-specific/service-specific eval, 운영 pipeline/VLOps, human+LLM feedback | eval candidate→judge→summary + structural metrics + real annotations + regression. 로컬 실험 파일/SQLite 저장; 상용 VLOps 운영 서비스 미배포 |
| 47–50 | 역할극 benchmark의 UX 한계, PersonaGym/Character-LLM | PSV-9+창업 task metrics. 개인 성격 정확도만으로 시장 유효성 평가하지 않음. NSona가 검토한 50여 연구 원목록이 PDF에 없으므로 그 목록 전체를 재현했다고 주장하지 않음 |
| 51 | 9축 rubric과 baseline persona | 1–5 rubric, card/state/기준 응답 schema. baseline을 강한 확신이나 문장 길이로 평가하지 않음 |
| 52–53 | human Gold: 사건→감정/원인→의미→가치·동기 | timeline 근거 + reasoning rules; Gold rationale/증거/허용 추론/금지 날조. 사건 없는 L0는 사실 회고 N/A |
| 54 | 독립 judge 3개, majority, A/B swap | 기존 eval 옵션 유지. 같은 모델 seed만 다르면 모델 차원 독립성은 제한적이라고 명시 |
| 55 | 상용6/경량6 모델 비교 | 4B/9B 동일 카드/seed/budget 비교 계획. 원본 익명 모델 A–F를 Qwen에 대응시키지 않음 |
| 56–58 | 품질·TTFT·비용 패턴, 과업별 최적 선택 | usage/latency 기록, PSV-9/task score 분리. FGI/심층인터뷰 우선; 디자인 선호 조사·vision은 다른 평가 필요. ‘큰 모델=좋은 persona’ 가정 금지 |
| 59–60 | 객관 baseline, prompt 개선, 데이터 축적 후 fine-tuning | benchmark/실자료 calibration→prompt loop→training scaffold. 이번 작업에서 training 실행하지 않음 |
| 61–67 | 디자이너/엔지니어 협업, evolving tool, 마무리/Q&A | 설계 문서 먼저 고정→구현→회귀/실Qwen→STATUS. 발표 마무리는 기능 없음 |

## NSona 9축 전체 crosswalk

| 원본 축 | PSV-9 대응/추가 관찰 |
|---|---|
| 정합성 | Evidence-grounded Persona Fidelity; 역할·rule 근거 |
| 재현성 | Persona Fidelity의 말투·관점 재현. 동일 seed/카드 반복의 생성 일관성은 별도 관찰이며 원본 축과 동일시하지 않음 |
| 독립적 일관성 | Cross-turn Consistency, Multi-party Independence; majority imitation 금지 |
| 경험 회고성 | Problem Experience Specificity + Epistemic Restraint; timeline 사건·원인·의미. 근거 없는 회고는 감점/N/A |
| 니즈 표출성 | Need Articulation + Decision Realism; 기능/감정/사회 목표는 자료 또는 표시된 가설 |
| 발산적 사고력 | Need Articulation + Grounded Disagreement; novel useful insight task metric. 없는 기능/경험 발명은 점수 아님 |
| 상호작용적 자기정교화 | Multi-party Independence & Refinement; reply, 정정 기회, stance revision 이유 |
| 비동조성 | Non-sycophancy + Grounded Disagreement; 억지 반대도 감점 |
| UX/UI 인식 및 맥락 해석력 | 텍스트 서비스 조건은 Decision Realism; 실제 이미지 해석은 현재 N/A. PSV 평균에 가짜 vision 점수를 넣지 않음 |

## 명시한 문헌 — 확인한 결과, 적용, 한계

각 링크는 저자 논문/학회/출판사다. 고전 대화 분석은 설명 이론이며 우리 AI의 유효성을 실증한 연구가 아니다. 책은 접근 가능한 서지·관련 발췌 범위에서 검토했으며 전권을 읽었다고 주장하지 않는다.

1. [Adriansen, 2012, Timeline interviews](https://tidsskrift.dk/qual/article/view/6272), Qualitative Studies 3(1), 40–55. 사건을 사회적 맥락과 연결하는 인터뷰 방법이며 선형성·일관성을 강요하지 말라고 설명한다. → 근거 있는 timeline와 조건부 해석 분리. AI의 실제 심리/동기를 증명하지 않음. 저자는 Hanne Kirstine Adriansen 단독이다.
2. [Shin et al., DIS 2024](https://users.aalto.fi/~luceroa1/publications/2024/shin24_persona.pdf), DOI 10.1145/3643834.3660729. 사람의 자료 분류와 LLM 요약을 나누는 workflow를 비교했다. → 사용자가 타깃/근거를 선택하고 structured Builder/Validator를 사용한다. 이 논문의 Study 1–4와 NSona 슬라이드의 prompt 실험 1–4는 서로 다른 실험이다. 생성 규칙만으로 환각이 완전히 방지됐다고 해석하지 않는다.
3. [Chen et al., CHI HEAL workshop 2024](https://heal-workshop.github.io/chi2024_papers/35_evaluating_the_llm_agents_for_.pdf). 847 검색→중복 제거815→최종45; agent-oriented와 task-oriented 측정의 간극을 설명한다. → Fidelity/consistency/hallucination/diversity 등과 실제 인터뷰 usefulness를 분리. workshop review이고 선별 연구 대다수가 당시 preprint였다. 815편을 모두 실증 검증한 결과라는 뜻이 아니다.
4. [Sacks, Schegloff & Jefferson, Language 1974](https://pure.mpg.de/pubman/item/item_2376846_3/component/file_2376845/Sacks_1974_simplest_systematics.pdf). 현재 화자의 다음 화자 선택, 자기 선택, 현재 화자 계속의 순서와 국소적 턴 조직. → 지명된 답 우선·완성 메시지 경계·recency 제어. 순차 텍스트 시스템이 인간의 겹침/운율을 재현한다고 주장하지 않음.
5. Sinclair & Coulthard, OUP 1975, *Towards an Analysis of Discourse*. [저자들의 관련 장을 수록한 Routledge 1992](https://www.routledge.com/Advances-in-Spoken-Discourse-Analysis-1st-Edition/Coulthard/p/book/9780415066877) 서지/목차 확인. → initiation/response/follow-up의 운영 단위를 참고한다. 교실의 teacher evaluation을 창업자가 persona를 채점하는 권력 구조로 복제하지 않는다. 원전 전권 접근 미확보.
6. [Goffman, Penn Press 1981, Forms of Talk](https://www.pennpress.org/9780812211122/forms-of-talk/). 발화의 맥락/participation 관점. → 화자와 수신자/관찰자를 구분하고 다른 참여자의 말을 자기 경험으로 전환하지 않음. 책 전체에 대한 구현 동등성 주장을 하지 않음.
7. [Schegloff, Cambridge 2007, Sequence Organization](https://www.cambridge.org/core/books/abs/sequence-organization-in-interaction/adjacency-pair-as-the-unit-for-sequence-construction/9AFC5658125C316C1A0FDE9DE4027C6D), [1–3장 발췌](https://icar.cnrs.fr/ecole_thematique/tranal_i/documents/org_seq/schegloff07_chap1-3.pdf). → 질문–응답 pair/확인 확장/종료, bounded expansion, 미응답을 해결로 간주하지 않는 thread ledger. max4는 논문이 정한 숫자가 아니라 로컬 비용 상한이다.
8. [Hilgert & Niehues, ICNLSP 2025](https://aclanthology.org/2025.icnlsp-1.7/). 다도메인 NSP benchmark와 전용 학습 시스템, 11명 human baseline. → 생성과 다음 화자 선택을 분리하고 directed-recipient/스케줄을 평가. 그들의 fine-tuned NSP 성능을 우리의 heuristic controller 성능으로 주장하지 않음.
9. [Umair, Sarathy & de Ruiter, EMNLP Findings 2024](https://aclanthology.org/2024.findings-emnlp.909/). spoken TRP 예측의 LLM 한계. **NSona p37의 2022 표기는 공식 발표와 다르므로 2024로 정정.** → 자동 끼어들기/가짜 대화 지연 없이 사용자 전송과 완성 메시지를 경계로 사용. 우리 모델은 audio TRP 모델이 아니다.
10. [Ma, Zhang & Zhao, ACL 2022](https://aclanthology.org/2022.acl-long.23/), [저자 code](https://github.com/xbmxb/StructureCharacterization4DD), 그리고 [Jia et al., EMNLP 2020](https://aclanthology.org/2020.emnlp-main.150/), [저자 code](https://github.com/JiaQiSJTU/ResponseSelection). 화자/참조 구조와 dependency thread의 중요성을 평가한 별개 두 연구다. → thread_id/reply_to/수신자와 active-thread context를 구현. Ubuntu/retrieval 실험 결과는 창업 인터뷰의 우월성 증거가 아니다. 학습된 구조 네트워크나 Thread Encoder weights는 이 MVP에 가져오지 않았다.

## 추가 직접 참고

- NSona p19의 [Spotting Out-of-Character Behavior, Jisu Shin et al., ACL Findings 2025](https://aclanthology.org/2025.findings-acl.1349/): 원자 단위 persona alignment와 생성 내/생성 간 일관성을 구분한다. 슬라이드의 2024는 공식 2025 서지와 다르며 DIS 논문의 Joongi Shin과도 다른 저자다. → 문장별 claim/grounding/조건부 해석/모순을 annotation으로 평가하는 `eval/persona_atoms.py`. 논문의 성격 척도 ACCatom/ICatom/RCatom 계산을 재현했다고 부르지 않는다.
- NSona p19의 [Kitzinger, BMJ 1995, Introducing focus groups](https://www.bmj.com/content/311/7000/299.abstract): 참여자가 서로 묻고 경험·관점에 반응하는 상호작용이 연구 방법의 일부다. → 개별 순차 답변만 모으는 구조 대신 지명 질문·조건 비교·정정 확장. 인간 focus group 방법을 근거로 AI 3명이 실제 고객보다 유효하다고 주장하지 않는다.
- NSona p19의 [Sanders & Stappers, CoDesign 2008](https://research.tudelft.nl/en/publications/co-creation-and-the-new-landscapes-of-design/): 참여적 디자인의 역할/공동 창작 관점. → 사용자의 타깃 선택·카드 편집·질문 선택 권한 유지. 인간의 공동 창작 역할을 가상 persona의 상업적 동의로 대체하지 않는다. 이번 버전은 startup interview이며 이미지 co-creation 과제는 보류다.
- [PersonaGym 저자 프로젝트](https://personagym.com/), [MIT code](https://github.com/vsamuel2003/PersonaGym): 2024 preprint, 저장소는 EMNLP Findings 2025판을 안내한다. 상황별 action justification/consistency를 평가하는 방법 → condition→choice rule, 상황 변화/거짓 전제 Gold. PersonaScore가 시장 recall은 아니다. 코드/데이터를 복사하거나 유료 API를 기본 의존성으로 추가하지 않는다.
- [Baltaji et al., C3NLP 2024](https://aclanthology.org/2024.c3nlp-1.2/): 그룹 의견의 동조/근거 없는 답 위험 → private pre/post, revision reason, conformity 평가. 상호작용을 항상 늘리지 않고 질문당 상한/사용자 차례를 둔다.
- [Schegloff & Sacks, 1973, Opening Up Closings](https://web.stanford.edu/~eckert/Courses/l1562018/Readings/SchegloffSacks1973.pdf): 종료 전 남은 문제와 종료의 조직 → pre-closing check 후 사용자에게 미해결 항목 보존. 종료 문구만 붙이는 것으로 인간 종료를 증명하지 않음.

## 구현·평가 책임

`schemas.py/services.py`: 표시 이름, 사실과 판단 가설, timeline, 별도 검증. `guided.py`: 질문 추천, WAITING/thread/finish. `context.py/adaptive.py`: 수신자·reply·개인/공개 기억. `frontend`: 이름/역할/예시군·프로필·추천칩·사용자 종료. `eval/conversation_metrics.py`: 자동 구조 점검과 별도 human 항목. 실제 수행 결과와 남은 항목은 STATUS에 기록한다. 코드 통과, 실제 Qwen 연결, 실증 품질 검증을 서로 다른 완료 상태로 유지한다.
