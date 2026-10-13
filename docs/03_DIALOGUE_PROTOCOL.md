# Dialogue protocol v2

2026-10-12 current override: [protocol 6 depth contract](21_DIALOGUE_DEPTH.md) replaces v5's usual 2n / maximum 3n per-message limit with content-dependent clarification, cross comparison, return/refinement and decision probes (safety ceiling 5n). Human-led composer, independence, private separation and report snapshots remain.

2026-10-04 current override: [v5 continuous-chat contract](15_CONTINUOUS_CHAT_REVISION.md) supersedes v1–v4 display/start/follow-up/closure rules below. Name + segment only; selection → same normal composer; all-selected contribution/grounded peer comparison, default 2×n and maximum 3×n public turns per message; optional revision-bound report snapshot, continued chat and no automatic report per message. Earlier fixed v2/A–D and automatic v3 remain compatibility/evaluation paths. Historical measurements are not v5 validation.

Historical v3 product sessions created on 2026-10-03 used [adaptive protocol v3](12_ADAPTIVE_CONVERSATION.md). This fixed protocol remains for saved v2 sessions and controlled A-D evaluation only. Follow-up conversations use v3 for both versions.

Explicit state machine: CREATED → PRE → GROUP → POST → REPORT → COMPLETE (or FAILED). No LLM routing graph. One shared model, sequential calls, three independent contexts.

Private pre asks initial need, alternative, constraint and provisional stance. Six group rounds:

| Round | Moderator question |
|---|---|
| Problem Reality | What is the problem, when does it matter, what is unknown? |
| Solution Reaction | Under your conditions, would this proposed approach help? |
| Cross-reaction | Which other participant's reason applies or does not apply to you? |
| Conflict Probe | Where do the conditions differ? Do not invent conflict. |
| Adoption/Payment Reality | Who decides/pays, what alternative and switching cost matter? |
| Failure Condition | What would make this fail or make you reconsider? |

Default: 3 speakers per round for three cards (18), 2 per round for two (12), two followups per round for one (12). One utterance per selected speaker per round when ≥2. Speaker score = question relevance + grounded disagreement strength + direct mention + unresolved issue - recent-speaking penalty; deterministic ties by ID. Scheduling is bounded and fairness-constrained. Explicit recipient/reply_to must refer to existing group utterance.

Private post: final stance, what changed, why, remaining unknowns, real interview checks. Changes require reasons; no majority imitation. Group visibility is bounded recent messages plus attributed older summary. Own private memory is separate. Public recent window 6 turns/900 chars summary, own recent window 4 turns/600 chars summary; card + state + current question added. Old summary must retain attribution and must never turn a group's claim into personal experience. Token-budget packing removes duplicated fields, summarizes older turns and marks reduced excerpts; immutable core constraints remain protected. See docs/11_STABILITY_DIALOGUE_REVISION.md for nomination, independence, timing and repair rules.

Historical v4 default: validated selection → Qwen question plan → private pre → WAITING → human question/active thread/at most4 peer responses → WAITING → human finish/pre-closing/private post/report. Automatic v3 remains selectable. Thread ancestry, recipients, remaining issues and resume cursor persist. See [v4 contract](13_PERSONA_LOUNGE_DESIGN.md).
