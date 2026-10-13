# Data contract v1

2026-10-04 current override: [v5 continuous-chat contract](15_CONTINUOUS_CHAT_REVISION.md) supersedes v1–v4 display/start/follow-up/closure rules below. Name + segment only; selection → same normal composer; all-selected contribution/grounded peer comparison, default 2×n and maximum 3×n public turns per message; optional revision-bound report snapshot, continued chat and no automatic report per message. Earlier fixed v2/A–D and automatic v3 remain compatibility/evaluation paths. Historical measurements are not v5 validation.

Evidence levels: L0 model prior; L1 supplied public market document; L2 founder-supplied customer/market data; L3 real interview transcript; L4 observed behavior. Level records provenance type, not automatic truth or probability. Sources require ID, text, level, consent/licensing note; no automatic promotion. Interview summaries reported by founder remain L2 until transcript exists.

Grounding data (runtime context), training data (behavior demonstrations), evaluation data (held out) are separate directories and source-ID splits. No automatic use of user sessions for training. Minimize personal data; obtain permission before using transcripts; redact identifying details before local import. Delete session via API removes session record. Source IDs and hashes retained for audit.

Stored session: input, brief, targets, validated cards, transcript(id, persona_id, phase, round, question, content, stance, reason, reply_to, evidence_ids), independent states, report, model mode/usage/latency, state history. SQLite JSON persistence is local and restart-safe.

Eval JSONL: case_id, dataset_kind(synthetic/human), source_split, idea, card(s), question, history, gold_response(nullable), gold_origin, human_annotations. Annotation fields: predicted/real themes, valid/false/novel IDs, alternatives, barriers, contradictions, supported IDs, pre/post stance with reason assessment, founder usefulness, predicted confidence and real observed labels. Missing human annotations yield null metrics, not zero or synthetic ground truth.

Training SFT: source_id, split, card, messages, target response, behavior tags. Preference: source_id, split, prompt/card, chosen, rejected, rationale. Scripts reject source overlap with evaluation and unmarked synthetic data.

Revision4: cosmetic presentation; immutable hypothesis rules and evidence-only timeline; QuestionSuggestion(topic/question/why/persona_id); ConversationThread(root question/utterance IDs/status/stop_reason/remaining_issues). Utterance adds thread_id/reasoning_rule_ids/quality_flags/generated_content. Raw overclaim text is stored for audit, excluded from model conversation history. Thread IDs refer only to public utterances; source levels never promote from discussion.
