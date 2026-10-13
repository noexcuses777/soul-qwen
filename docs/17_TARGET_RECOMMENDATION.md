# Target recommendation contract (2026-10-04)

The first recommendation answers **who could use, introduce or buy this idea**, not what to research. The button says `타깃 추천받기`; selecting up to three targets is followed by persona generation and independent persona validation. The name/segment presentation after selection remains unchanged.

- `segment_name`: a concrete potential participant group, described by activity or organizational context. A feature, interview question, validation task, pricing model or metric cannot occupy this field.
- `why_relevant`: why this participant could encounter the founder's problem or be involved in adoption. `problem_exposure` describes that situation; `expected_current_alternative` remains a hypothesis or UNKNOWN. The internal buying role is separate from the segment name.
- Exactly six initial candidates are generated from the supplied idea. No fixed list of customers is substituted when Qwen fails. Contrast remains based on exposure, alternatives and decision conditions, not demographics.
- Check input limits and source IDs/levels, then perform one independent, compact batch review of participant identity and plausible idea relevance. Review must cover every candidate exactly once. A narrow local guard additionally rejects bare task/topic labels. This guard is not a universal semantic classifier.
- If the generated batch fails the semantic check or has fewer than three distinct decision/exposure profiles, provide its concrete issues to one regeneration attempt and review that attempt. At most two generator/reviewer attempts; never retry indefinitely or quietly use mock customers.
- Store successful/failed candidate batches and reviews in `target_audits` when a recommendation eventually succeeds. Reusing an unchanged approved target avoids an extra selection review. New/edited or legacy unreviewed selections receive one batch review before any persona building; user-authored targets are rejected with an editable error, never silently rewritten.
- A `CREATED` session without personas/transcript can explicitly regenerate its recommendations using its stored idea. Keep the replaced batch in the audit trail; write the new batch only after success. Selected personas or started conversations cannot be changed by this endpoint. Existing sessions remain readable.

UI cards explicitly label the participant group, recommendation reason, problem situation and expected alternative. A separate `타깃 다시 추천받기` action repairs a previously saved bad batch. Removing the word “hypothesis” from the button does not raise evidence levels: without source data recommendations stay L0/low. Semantic review establishes the type of the recommendation, **not actual target accuracy, customer demand or persona fidelity**. Automated fixtures and a real Qwen smoke are recorded separately.

## Integration fixes found during real Qwen verification

Long recommendation reasons/situations/expected alternatives use multiline fields. Selection reads both inputs and textareas, preserves user edits and rejects missing participant/reason fields. Static UI assets are versioned so a normal refresh fetches the new layout.

The first real selection attempt revealed fabricated reasoning-rule source IDs and three failed builds. The builder request grammar now permits only supplied IDs for rules/anchors, and only L2+ source IDs for timeline events. With no sources, rule evidence IDs, anchors and timeline are constrained to empty lists. The prompt distinguishes hypothetical basis_fields from source IDs. The existing exact-quote/UNKNOWN validator remains in place; this does not establish full semantic fidelity. The failed attempt is preserved separately from the successful rerun.
