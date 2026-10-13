# Persona Studio product contract v5

Target recommendation revision: the CTA is `타깃 추천받기`. Candidates describe potential people/groups/organizations who could use or adopt this idea, never research tasks. Up to three remain human-selected. Independent batch review, one bounded regeneration, explicit pre-selection recovery and L0 evidence semantics are specified in [docs/17](17_TARGET_RECOMMENDATION.md).

2026-10-04 current override: [v5 continuous-chat contract](15_CONTINUOUS_CHAT_REVISION.md) supersedes v1–v4 display/start/follow-up/closure rules below. Name + segment only; selection → same normal composer; all-selected contribution/grounded peer comparison, default 2×n and maximum 3×n public turns per message; optional revision-bound report snapshot, continued chat and no automatic report per message. Earlier fixed v2/A–D and automatic v3 remain compatibility/evaluation paths. Historical measurements are not v5 validation.

Historical v4 contract (2026-10-03): [v4 설계](13_PERSONA_LOUNGE_DESIGN.md)가 기본 제품 동작이다. 개인 이름 + 예시군/역할군, 직접 질문 + Qwen 추천 → WAITING → 사용자가 종료 → private post/report. 자동 v3는 선택 기능, v2는 기존 세션·통제 평가용. 12–18 공개 발화는 자동 모드의 기본 목표이며 직접 질문 모드에 강제로 적용하지 않는다. [NSona 전 범위 대응과 1차 문헌](14_NSONA_RESEARCH_AUDIT.md) 참조.

Source priority: latest explicit user requirements (SOUL integration on 2026-10-05, see 18_SOUL_INTEGRATION.md) > earlier user requirements > attached Persona Studio PDF > NSona reference. Original PDFs remain in the original local Persona Studio workspace and are not included in the public integration branch; page-level review is in `SOURCE_REVIEW.md`. Business positioning: early founders use it; startup support institutions initially pay (Persona Studio pp.6-9). No pricing or procurement assumptions are supplied.

## Required flow
Idea Input Q1-Q5 → IdeaBrief → Target Hypotheses → user selects/edits/adds 1-3 → Persona Builder → separate Validator with bounded repair → Private Pre → Group → Private Post → Comparison Report → real interview Calibration. Target selection is always a human step; API must not automatically pick three.

Q1 one-line idea; Q2 background; Q3 section heading; Q3-1 distinction/problem; Q3-2 revenue; Q4 section heading; Q4-1 commercialization; Q5 mandatory category. Categories: IT, 교육, 금융, 운영관리, 네트워킹, 농업/축산업, 라이프스타일, 모빌리티, 마케팅/PR, 미디어/엔터테인먼트, 바이오/의료, 에너지/자원, 유통/물류, 임팩트, 재무, 프롭테크, 하드웨어, 기타, 패션, F&B, 뷰티, 생활.

Every result is a hypothesis. No simulated willingness-to-pay is a purchase commitment. Display mode (mock/Qwen), source level, unknowns, and next real interview questions. Explicitly reject claims of market validation from AI-only output. MVP acceptance: persisted selected cards, isolated states, 12-18 group utterances, all eight report sections, traceable utterance IDs, offline mock E2E, calibration with annotated real observations, runnable eval.

MVP is local single-user. No login/billing/recruitment integrations, crawling or cloud publication. Institution licenses and individual subscriptions remain business roadmap items, not fabricated working payment features.
