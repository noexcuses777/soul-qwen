# Persona schema v1

Target recommendation revision: `Target.segment_name` answers WHO, separate from reason, problem situation and internal buying role. Session adds backward-compatible `target_audits` (candidate batches, typed per-index participant/idea-fit reviews and issues); old sessions default to an empty list. A reviewed target is copied exactly into the persona identity segment. See [docs/17](17_TARGET_RECOMMENDATION.md).

2026-10-04 current override: [v5 continuous-chat contract](15_CONTINUOUS_CHAT_REVISION.md) supersedes v1–v4 display/start/follow-up/closure rules below. Name + segment only; selection → same normal composer; all-selected contribution/grounded peer comparison, default 2×n and maximum 3×n public turns per message; optional revision-bound report snapshot, continued chat and no automatic report per message. Earlier fixed v2/A–D and automatic v3 remain compatibility/evaluation paths. Historical measurements are not v5 validation.

NSona Who/What/How maps to Identity/Context, Problem Context, Decision Model, Goals/Motivations, Evidence Anchors, Interaction Style. Add Immutable Core and independent Session State.

| Block | Fields and constraints |
|---|---|
| Identity/Context | segment, role, use_context; age/gender/income UNKNOWN unless supplied with evidence |
| Problem Context | current_alternative, problem_severity, frequency, trigger; absence = UNKNOWN |
| Decision Model | adoption_barrier, buying_role, switching_cost, budget_constraint, decision_criteria |
| Goals/Motivations | desired_outcome, priority, risk_tolerance |
| Evidence Anchors | source_id, field, quote, level; no fabricated source IDs |
| Interaction Style | concise natural speech, directness, expression; cannot override honesty |
| Immutable Core | serialized frozen core blocks; never rewrite during interview |
| Session State | stance, reasons, unresolved_issues, observed group claims, revisions; per agent only |

Unknown strings use literal `UNKNOWN`; absent lists are empty. L0 fields are explicitly hypothetical, never lived experience. Persona Builder initially projects target claims conservatively then separate validator audits unsupported specifics, contradictions, stereotypes, similarity, forced pro/con and unknown handling. Failed audit: regenerate at most twice; final failure blocks interview. User edits must pass same validator.

No demographic inference of behavior. Contrast is in exposure/current alternative/buying role/barrier, not invented names/age. Private pre/post are never shared with other personas. Group messages are observations, never upgrades to evidence. Card fingerprint remains identical throughout session.

Revision2: optional occupation/life stage/region/technical literacy/domain experience; workaround/past failed attempts; risk sensitivity/authority/must have/rejection conditions; functional/emotional/social goals/motivation; stable profile values/constraints/preferences/history; richer interaction style. All factual additions require anchors or UNKNOWN/empty. style is a simulation delivery instruction, not an inferred trait. Optional unknown fields are omitted from prompts, populated by Pydantic defaults in saved cards.

Revision4: `presentation.display_name` is a fictional editable alias outside immutable core. `reasoning_rules` contains 1–2 conditional interpretation hypotheses (trigger/value/tradeoff/choice/basis/unknowns); factual fields retain the evidence gate. `timeline` contains only supplied source quotes with supported dates or UNKNOWN. See docs/13 and docs/14.

New recommendations now receive unique random Korean aliases (768 cosmetic combinations) stored in `Session.target_display_names`. Selected cards reuse those aliases; reloads, card order and user renames preserve identity. Explicit re-recommendation receives a fresh name set. Names never encode demographics, enter target evaluation, alter Immutable Core, or serve as customer evidence. Existing saved names remain unchanged; legacy missing aliases use the session UUID for stable recovery without a read-time database write.
