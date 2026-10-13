"""SOUL's report screen: a citation-preserving projection, with no extra model call.

Counts describe the selected synthetic participants and the saved report snapshot.
They are never estimates of a real market or evaluations of persona fidelity.
"""
from collections import OrderedDict
from .schemas import SECTIONS
from .services import guard_report_consensus, guard_report_quantities, report_quantity_basis
from .quantities import unsupported_quantities

STANCE_LABELS = {
    'unknown': '판단 보류', 'conditional': '조건부',
    'positive': '긍정', 'negative': '부정',
}


def is_question_draft(text):
    """Narrow display filter for question/request forms, not a semantic classifier."""
    text = text.strip()
    if text.endswith(('?', '？')):
        return True
    compact = ''.join(text.rstrip('.!。').split())
    return compact.endswith(('나요', '까요', '습니까', '인지요', '알려주세요',
                             '설명해주세요', '말씀해주세요', '비교해주세요', '확인해주세요'))


def _snapshot_turns(session):
    public = [turn for turn in session.transcript if turn.phase == 'group']
    inferred = session.report_revision is None
    revision = session.report_revision
    if inferred:
        # Legacy automatic interviews did not store the revision. A stale legacy
        # report must not absorb questions asked after its first private post.
        if session.report_stale:
            post_index = next((i for i, turn in enumerate(session.transcript)
                               if turn.phase == 'post'), len(session.transcript))
            public = [turn for turn in session.transcript[:post_index]
                      if turn.phase == 'group']
        revision = len(public)
    public = public[:max(0, revision)]
    visible_ids = {turn.id for turn in public}
    for turn in session.transcript:
        if turn.phase == 'pre':
            visible_ids.add(turn.id)
        elif turn.phase == 'post' and (
                turn.snapshot_revision == revision or
                inferred and turn.snapshot_revision is None):
            visible_ids.add(turn.id)
    # In inferred stale legacy snapshots, retain only posts before resumed chat.
    if inferred and session.report_stale:
        first_post = next((i for i, turn in enumerate(session.transcript)
                           if turn.phase == 'post'), len(session.transcript))
        next_public = next((i for i in range(first_post, len(session.transcript))
                            if session.transcript[i].phase == 'group'), len(session.transcript))
        visible_ids -= {turn.id for turn in session.transcript[next_public:]
                        if turn.phase == 'post'}
    return public, [turn for turn in session.transcript if turn.id in visible_ids], revision, inferred


def report_view(session):
    """Project an existing report. Never mutate its source or create conclusions."""
    if session.report is None:
        raise ValueError('대화를 진행한 뒤 리포트를 먼저 생성하세요.')
    # Old saved reports can predate the consensus citation guard. Apply the
    # existing guard to a detached copy so this read does not rewrite history.
    public, visible, revision, inferred = _snapshot_turns(session)
    detached = session.model_copy(deep=True)
    projected_report = guard_report_quantities(detached,
        guard_report_consensus(detached, session.report.model_copy(deep=True)), revision=revision)
    cards = {card.id: card for card in session.cards}
    turns = {turn.id: turn for turn in visible}
    evidence = {source.source_id: source for source in session.input.evidence}
    names = {card.id: card.presentation.display_name or card.id for card in session.cards}

    def participant(pid):
        card = cards.get(pid)
        return {'id': pid, 'name': names.get(pid, pid),
                'segment': card.immutable_core.identity_context.segment if card else 'UNKNOWN'}

    def position(turn):
        identity = participant(turn.persona_id)
        return {'persona_id': turn.persona_id, 'name': identity['name'],
                'segment': identity['segment'], 'stance': turn.stance,
                'stance_label': STANCE_LABELS[turn.stance], 'content': turn.content,
                'reason': turn.reason, 'utterance_id': turn.id,
                'evidence_ids': [sid for sid in turn.evidence_ids if sid in evidence],
                'quality_flags': list(turn.quality_flags)}

    sections = {}
    excluded = 0
    for name in SECTIONS:
        rows = []
        for insight in projected_report.sections[name]:
            if (not set(insight.utterance_ids) <= set(turns) or
                    not set(insight.evidence_ids) <= set(evidence) or
                    name != 'Real Interview Next Steps' and not insight.utterance_ids):
                excluded += 1
                continue
            rows.append({**insight.model_dump(mode='json'), 'section': name})
        sections[name] = rows

    grouped = OrderedDict()
    thread_lookup = {thread.id: thread for thread in session.threads}
    legacy_keys = {}
    for turn in public:
        if turn.thread_id:
            key = turn.thread_id
        else:
            # Automatic/legacy rounds are one question group, not separate
            # questions for every controller-generated cross-reaction prompt.
            if turn.round == 'Founder Follow-up':
                key = legacy_keys.get(turn.reply_to) or 'legacy:' + turn.round + ':' + turn.question
            else:
                key = 'legacy:' + turn.round
            legacy_keys[turn.id] = key
        if key not in grouped:
            thread = thread_lookup.get(key)
            grouped[key] = {'id': key, 'question': thread.question if thread else turn.question,
                            'turns': []}
        grouped[key]['turns'].append(turn)

    topics, changes = [], []
    for group in grouped.values():
        topic_turns = group['turns']
        topic_ids = {turn.id for turn in topic_turns}
        latest = OrderedDict()
        for turn in topic_turns:
            latest[turn.persona_id] = turn
        topics.append({'id': group['id'], 'question': group['question'],
                       'utterance_ids': [turn.id for turn in topic_turns],
                       'positions': [position(turn) for turn in latest.values()],
                       'insights': [row for rows in sections.values() for row in rows
                                    if topic_ids.intersection(row['utterance_ids'])]})
        before_by_person = {}
        for turn in topic_turns:
            before = before_by_person.get(turn.persona_id)
            guarded = any(flag.endswith('_withheld') or flag in (
                'unsupported_experience', 'purchase_overclaim') for flag in turn.quality_flags)
            if (before and before.stance != turn.stance and
                    before.stance != 'unknown' and turn.stance != 'unknown' and
                    turn.reason.strip() not in ('', 'UNKNOWN') and not guarded):
                def change_side(source):
                    return {key: value for key, value in position(source).items()
                            if key in ('utterance_id', 'stance', 'stance_label', 'content', 'reason')}
                changes.append({'persona_id': turn.persona_id,
                                'name': names.get(turn.persona_id, turn.persona_id),
                                'topic_id': group['id'], 'question': group['question'],
                                'before': change_side(before), 'after': change_side(turn),
                                'utterance_ids': [before.id, turn.id],
                                'basis': '같은 질문 묶음의 입장 표현과 이후 발화의 판단 이유를 비교했습니다. 변화 원인이나 동조가 입증된 결과는 아닙니다.'})
            if not guarded:
                before_by_person[turn.persona_id] = turn

    unknowns = OrderedDict()
    def unknown(text, utterance_ids=(), evidence_ids=()):
        text = text.strip()
        if not text or text == 'UNKNOWN':
            return
        row = unknowns.setdefault(text, {'text': text, 'utterance_ids': [], 'evidence_ids': []})
        row['utterance_ids'] = list(dict.fromkeys(row['utterance_ids'] + list(utterance_ids)))
        row['evidence_ids'] = list(dict.fromkeys(row['evidence_ids'] + list(evidence_ids)))
    for row in sections['Unknown/Unsupported']:
        unknown(row['text'], row['utterance_ids'], row['evidence_ids'])
    for turn in public:
        for issue in turn.unresolved_issues:
            unknown(issue, [turn.id])
    # Thread-level pending conditions can survive a response budget without
    # becoming an actual utterance. Keep them without fabricating a quote ID.
    for key, group in grouped.items():
        thread = thread_lookup.get(key)
        if thread and set(thread.utterance_ids) <= {turn.id for turn in public}:
            for issue in thread.remaining_issues:
                unknown(issue)

    followups = []
    seen_questions = set()
    for turn in public:
        question = turn.followup_question.strip()
        answered = any(answer.reply_to == turn.id and answer.persona_id == turn.addressed_to
                       for answer in public)
        if (not question or not is_question_draft(question) or
                unsupported_quantities(question, report_quantity_basis(session, [turn.id], revision)) or
                question in seen_questions or answered or
                turn.followup_kind == 'none' or any(flag.endswith('_withheld') for flag in turn.quality_flags)):
            continue
        seen_questions.add(question)
        followups.append({'question': question, 'topic_id': turn.thread_id,
                          'persona_id': turn.addressed_to, 'utterance_ids': [turn.id],
                          'kind': turn.followup_kind, 'why': turn.reason})
    # Cached suggestions have no revision metadata. Do not introduce potentially
    # newer suggestions into an older report snapshot.
    if not session.report_stale:
        for suggestion in session.suggestions:
            if (is_question_draft(suggestion.question) and suggestion.question not in seen_questions and
                    not unsupported_quantities(suggestion.question, report_quantity_basis(session, revision=revision))):
                seen_questions.add(suggestion.question)
                followups.append({'question': suggestion.question, 'topic_id': None,
                                  'persona_id': suggestion.persona_id, 'utterance_ids': [],
                                  'kind': 'suggestion', 'why': suggestion.why})

    new_insights = sections['Problem Signal'] + sections['Target Differences']
    notice = projected_report.notice
    if inferred:
        notice += ' 이전 형식의 리포트이므로 공개 발화 범위를 저장된 대화 순서에서 복원했습니다.'
    if excluded:
        notice += ' 현재 리포트 범위에서 인용을 확인할 수 없는 항목은 표시하지 않았습니다.'
    return {
        'meta': {'session_id': session.id, 'generated_at': session.report_generated_at,
                 'revision': revision, 'revision_inferred': inferred,
                 'stale': session.report_stale, 'persona_count': len(cards),
                 'question_count': len(topics), 'public_turn_count': len(public),
                 'insight_count': len(new_insights), 'change_count': len(changes),
                 'unknown_count': len(unknowns), 'excluded_insight_count': excluded,
                 'participants': [participant(card.id) for card in session.cards],
                 'metrics_notice': '선택된 AI 페르소나와 저장된 대화의 개수입니다. 시장 검증·구매 확률·인간 유사성 점수가 아닙니다.'},
        'notice': notice,
        'conclusion': sections['Solution Reaction'] + sections['Agreement'] + sections['Disagreement'],
        'topics': topics, 'new_insights': new_insights, 'changes': changes,
        'followups': followups, 'unknowns': list(unknowns.values()),
        'real_interview': sections['Real Interview Next Steps'], 'sections': sections,
        'sources': [{**position(turn), 'id': turn.id, 'phase': turn.phase,
                     'generated_content': turn.generated_content} for turn in visible],
        'audits': [audit for audit in detached.dialogue_runtime.get('report_claim_audits', [])
                   if set(audit.get('original_claim', {}).get('utterance_ids', [])) <= set(turns)],
    }
