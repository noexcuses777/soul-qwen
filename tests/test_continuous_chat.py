"""Continuous-chat control and grounding checks; fixtures do not score semantic quality."""
import copy
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.context import fingerprint, ContextManager, PersonaAgent
from backend.llm import LLMClient, LLMError
from backend.schemas import Session, Utterance, InteractionAnswer
from eval.conversation_metrics import structural_metrics


class ConversationTrace(LLMClient):
    """Trace real controller payloads, while serving explicitly synthetic answers."""
    def __init__(self, ongoing=True):
        super().__init__('mock')
        self.payloads = []
        self.interacts = 0
        self.fail_interact_at = None
        self.fail_report_once = False
        self.ongoing = ongoing

    def call(self, task, payload, schema, **kwargs):
        if task == 'report' and self.fail_report_once:
            self.fail_report_once = False
            raise LLMError('synthetic report interruption')
        if task in ('interact', 'chat'):
            self.interacts += 1
            if self.interacts == self.fail_interact_at:
                raise LLMError('synthetic response interruption')
        answer = super().call(task, payload, schema, **kwargs)
        if task in ('agent', 'interact', 'chat'):
            self.payloads.append(copy.deepcopy(payload))
        if task in ('interact', 'chat') and payload['round'] != 'Closing check':
            pid = payload['card']['id']
            peers = [p for p in payload.get('participants', []) if p != pid]
            step = payload.get('conversation_step', 'contribution')
            arguments = {
                'contribution': '가설로는 준비 부담이 줄어드는 경우에 검토할 수 있습니다. 새 과정이 기존 작업을 대체하는지에 따라 선택이 달라집니다.',
                'cross_response': '동료의 편의성 조건을 제 상황에 그대로 적용할 수는 없습니다. 판단 권한에 따라 사용 편의보다 설명 가능한 근거를 먼저 확인할 수 있습니다.',
                'clarification': '추가 업무가 되는 경우와 기존 작업을 대체하는 경우를 구분하겠습니다. 단순히 과정이 쉬워지는 것만으로 검증의 효과를 확정할 수는 없습니다.',
                'refinement': '앞선 편의성 판단을 좁히겠습니다. 준비가 쉬워지는 효과와 고객을 이해하는 효과는 다르므로, 기존 대안과 비교할 관찰 근거를 별도로 보겠습니다.',
                'decision_probe': '검증 자료를 준비하는 부담이 줄지 않으면 사용을 보류할 수 있습니다. 실제 고객에게 현재 판단 과정을 설명하게 하고, 새 도구로 달라지는 과정을 확인하겠습니다.',
            }
            questions = {
                'contribution': '새로운 과정이 기존 업무를 대체해야 한다는 조건을 어떻게 보시나요?',
                'cross_response': '어떤 판단 근거가 있어야 동료의 편의성 조건을 받아들일 수 있나요?',
                'clarification': '업무가 추가되는 상황에서는 선택을 어떻게 달리하시나요?',
                'refinement': '실제 고객에게 확인할 관찰과 가상의 판단을 어떻게 구분하시나요?',
                'decision_probe': '이 검토를 계속할 때 남는 준비 부담은 무엇인가요?',
            }
            role = payload['card']['immutable_core']['decision_model']['buying_role']
            answer.content = role + ' 조건에서 ' + arguments[step]
            answer.reason = '자기 역할의 준비 부담과 설명 가능한 판단 근거를 구분하는 synthetic 조건'
            answer.stance = 'conditional' if self.ongoing else 'unknown'
            answer.reasoning_rule_ids = ['r1']
            answer.unresolved_issues = ['새 과정이 기존 업무를 대체하는 조건'] if self.ongoing else []
            answer.dialogue_act = 'question' if self.ongoing and peers else 'answer'
            answer.addressed_to = peers[self.interacts % len(peers)] if peers else None
            answer.followup_question = questions[step] if self.ongoing and peers else ''
            answer.followup_kind = 'clarification' if self.ongoing and peers else 'none'
        return answer


def selected(tmp_path, llm=None, n=3):
    llm = llm or ConversationTrace()
    api = TestClient(create_app(str(tmp_path / 'continuous.db'), llm))
    created = api.post('/api/sessions', json={'q1': '고객 인터뷰 준비 도구', 'q5': 'IT'})
    assert created.status_code == 200, created.text
    base = f'/api/sessions/{created.json()["id"]}'
    response = api.post(base + '/select', json={'target_ids': [f't{i+1}' for i in range(n)]})
    assert response.status_code == 200, response.text
    return api, llm, base, response.json()


def successful(response):
    assert response.status_code == 200, response.text
    return response.json()


def thread_turns(session, index=-1):
    ids = set(session['threads'][index]['utterance_ids'])
    return [t for t in session['transcript'] if t['id'] in ids]


@pytest.mark.parametrize('n', [1, 2, 3])
@pytest.mark.parametrize('interaction', ['auto', 'interactive'])
def test_selected_personas_can_chat_immediately_and_all_take_part(tmp_path, n, interaction):
    api, llm, base, initial = selected(tmp_path, n=n)
    question = '현재 대안과 비교할 때 준비 노력과 효과를 어떤 조건에서 판단할까요?'
    session = successful(api.post(base + '/ask', json={'question': question, 'interaction': interaction}))
    turns = thread_turns(session)
    assert session['status'] == 'WAITING' and session['report'] is None
    assert {t['persona_id'] for t in turns} == {c['id'] for c in initial['cards']}
    assert (2*n if n>1 else 1) <= len(turns) <= 5*n
    assert sum(t['phase'] == 'pre' for t in session['transcript']) == n
    assert not any(r['task'] == 'questions' for r in llm.records)
    assert session['threads'][0]['status'] == 'returned_to_user'
    assert not structural_metrics(Session.model_validate(session))['invalid_reply_ids']
    if n > 1:
        assert any(t['reply_to'] for t in turns)
        assert all(sum(t['persona_id'] == c['id'] for t in turns) >= 2 for c in initial['cards'])
        assert {t['persona_id'] for t in turns if t['reply_to']} == {c['id'] for c in initial['cards']}
    hashes = [fingerprint(c) for c in Session.model_validate(initial).cards]
    assert [fingerprint(c) for c in Session.model_validate(session).cards] == hashes
    group_payloads = [p for p in llm.payloads if p['phase'] == 'group']
    assert group_payloads and all(p['dialogue_goal'] == question for p in group_payloads)
    for payload in group_payloads:
        assert all(t['phase'] == 'group' for t in payload['group']['recent'])
        assert all(t['persona_id'] == payload['card']['id'] for t in payload['own']['recent'])
        assert 'presentation' not in payload['card']


def test_direct_api_mode_remains_explicit_one_person_response(tmp_path):
    api, _, base, _ = selected(tmp_path)
    session = successful(api.post(base + '/ask', json={
        'question': '도입 조건은 알려졌나요?', 'persona_id': 'p2', 'interaction': 'direct'}))
    turns = thread_turns(session)
    assert len(turns) == 1 and turns[0]['persona_id'] == 'p2'
    assert session['status'] == 'WAITING'


def test_name_nomination_changes_first_speaker_without_excluding_other_personas(tmp_path):
    api, _, base, original = selected(tmp_path)
    renamed = successful(api.post(base + '/names/p3', json={'display_name': '민서준'}))
    hashes = [fingerprint(c) for c in Session.model_validate(original).cards]
    assert [fingerprint(c) for c in Session.model_validate(renamed).cards] == hashes
    result = successful(api.post(base + '/ask', json={'question': '민서준님, 준비 비용과 효과를 어떤 조건으로 비교할까요?'}))
    turns = thread_turns(result)
    assert turns[0]['persona_id'] == 'p3'
    assert {t['persona_id'] for t in turns} == {'p1', 'p2', 'p3'}
    assert [fingerprint(c) for c in Session.model_validate(result).cards] == hashes


def test_neutral_answers_still_allow_peer_comparison_without_forced_disagreement(tmp_path):
    api, _, base, _ = selected(tmp_path, ConversationTrace(ongoing=False))
    session = successful(api.post(base + '/ask', json={'question': '이 도구의 적용 범위를 비교해 주세요.'}))
    turns = thread_turns(session)
    assert {t['persona_id'] for t in turns} == {'p1', 'p2', 'p3'}
    assert any(t['reply_to'] for t in turns)
    assert all(t['dialogue_act'] not in ('disagree', 'question') for t in turns)
    assert 6 <= len(turns) <= 15
    assert all(sum(t['persona_id'] == pid for t in turns) >= 2 for pid in ('p1', 'p2', 'p3'))


def test_initial_contributions_stay_independent_then_cross_responses_get_exact_peer(tmp_path):
    api, trace, base, initial = selected(tmp_path, ConversationTrace(ongoing=False))
    question = '각자 자신의 현재 대안과 비교할 조건을 알려주세요.'
    first = successful(api.post(base + '/ask', json={'question': question}))
    trace.payloads = []
    second = successful(api.post(base + '/ask', json={'question': '이제 준비 노력과 효과를 다시 비교해주세요.'}))
    payloads = [p for p in trace.payloads if p['phase'] == 'group']
    contributions = [p for p in payloads if p['conversation_step'] == 'contribution']
    cross = [p for p in payloads if p['conversation_step'] == 'cross_response']
    assert len(contributions) == 3 and len(cross) == 3
    assert all(p['conversation_step'] == 'contribution' for p in payloads[:3])
    cards = {c['id']: c for c in initial['cards']}
    turns = {t['id']: t for t in second['transcript']}
    thread_ids = set(second['threads'][-1]['utterance_ids'])
    for p in payloads:
        own = cards[p['card']['id']]['immutable_core']
        frame = p['own_decision_frame']
        assert frame['persona_id'] == p['card']['id']
        assert frame['hypothetical_role'] == own['decision_model']['buying_role']
        assert frame['expected_alternative'] == own['problem_context']['current_alternative']
        assert frame['exposure'] == own['identity_context']['use_context']
        assert p['dialogue_goal'] == second['threads'][-1]['question']
        assert [r['id'] for r in p['card']['immutable_core']['reasoning_rules']] == [p['card']['id']+':'+r['id'] for r in own['reasoning_rules']]
        assert frame['rules'] == [{'id': p['card']['id']+':'+r['id'], **{key:r[key] for key in ('trigger','value','tradeoff','conditional_choice')}} for r in own['reasoning_rules']]
        pre = next(t for t in second['transcript'] if t['phase']=='pre' and t['persona_id']==p['card']['id'])
        assert p['private_baseline']['content'] == pre['content']
        assert set(p['state']) <= {'stance','note'}
    for p in contributions:
        assert p['group'] == {'older_summary': '', 'recent': []}
        assert 'required_parent' not in p
    for p in cross:
        assert p['group'] == {'older_summary': '', 'recent': []}
        parent = p['required_parent']
        assert parent['id'] in thread_ids and parent['persona_id'] != p['card']['id']
        assert parent['phase'] == 'group' and parent['content'] == turns[parent['id']]['content']
        peer = cards[parent['persona_id']]
        assert parent['speaker_alias'] == peer['presentation']['display_name']
        assert parent['hypothetical_role'] == peer['immutable_core']['decision_model']['buying_role']
        assert parent['expected_alternative'] == peer['immutable_core']['problem_context']['current_alternative']
        assert all(rid.startswith(peer['id']+':') for rid in parent['reasoning_rule_ids'])
        assert all(rule['id'] in parent['reasoning_rule_ids'] for rule in parent['reasoning_rules'])
        assert all(rule['id'].startswith(peer['id']+':') for rule in parent['reasoning_rules'])
    assert second['transcript'][:len(first['transcript'])] == first['transcript']
    assert [fingerprint(c) for c in Session.model_validate(second).cards] == [fingerprint(c) for c in Session.model_validate(initial).cards]


def test_mixed_unknown_card_contributes_but_is_not_forced_into_cross_expansion(tmp_path):
    api, trace, base, initial = selected(tmp_path, ConversationTrace(ongoing=False))
    session = Session.model_validate(initial)
    unknown = session.cards[2]
    core = unknown.immutable_core.model_dump()
    core['identity_context']['use_context'] = 'UNKNOWN'
    core['identity_context']['role'] = 'UNKNOWN'
    core['decision_model']['buying_role'] = 'UNKNOWN'
    core['reasoning_rules'] = []
    unknown.immutable_core = type(unknown.immutable_core).model_validate(core)
    api.app.state.store.put(session)
    result = successful(api.post(base + '/ask', json={'question': '각자의 조건을 구체적으로 비교해주세요.'}))
    turns = thread_turns(result)
    assert 5 <= len(turns) <= 15
    assert {t['persona_id'] for t in turns} == {'p1', 'p2', 'p3'}
    assert sum(t['persona_id'] == 'p3' for t in turns) == 1
    assert sum(t['persona_id'] == 'p1' for t in turns) >= 2
    assert sum(t['persona_id'] == 'p2' for t in turns) >= 2
    public = [p for p in trace.payloads if p['phase'] == 'group']
    assert not any(p['card']['id'] == 'p3' and p['conversation_step'] == 'cross_response' for p in public)
    assert fingerprint(Session.model_validate(result).cards[2]) == fingerprint(unknown)


def test_all_unknown_cards_do_not_manufacture_comparison(tmp_path):
    api, _, base, original = selected(tmp_path)
    session = Session.model_validate(original)
    for card in session.cards:
        raw = card.immutable_core.model_dump()
        raw['identity_context']['use_context'] = 'UNKNOWN'
        raw['identity_context']['role'] = 'UNKNOWN'
        raw['decision_model']['buying_role'] = 'UNKNOWN'
        raw['reasoning_rules'] = []
        card.immutable_core = type(card.immutable_core).model_validate(raw)
    api.app.state.store.put(session)
    result = successful(api.post(base + '/ask', json={'question': '조건의 차이를 비교해주세요.'}))
    assert {t['persona_id'] for t in thread_turns(result)} == {'p1', 'p2', 'p3'}
    assert len(thread_turns(result)) == 3
    assert result['threads'][-1]['stop_reason'] == 'no_grounded_expansion'


def test_interrupted_preparation_resumes_first_question_without_duplicate_pre(tmp_path):
    class FailPre(ConversationTrace):
        def __init__(self):
            super().__init__()
            self.pre_calls = 0

        def call(self, task, payload, schema, **kwargs):
            if task == 'agent' and payload.get('phase') == 'pre':
                self.pre_calls += 1
                if self.pre_calls == 2:
                    raise LLMError('synthetic pre interruption')
            return super().call(task, payload, schema, **kwargs)

    llm = FailPre()
    api, _, base, _ = selected(tmp_path, llm)
    question = {'question': '첫 질문을 계속 진행해주세요.'}
    assert api.post(base + '/ask', json=question).status_code == 502
    partial = api.get(base).json()
    assert len(partial['transcript']) == 1 and partial['transcript'][0]['phase'] == 'pre'
    resumed = successful(api.post(base + '/ask', json=question))
    assert resumed['transcript'][:1] == partial['transcript']
    assert sum(t['phase'] == 'pre' for t in resumed['transcript']) == 3
    assert len(resumed['threads']) == 1
    assert sum(e['role'] == 'founder' for e in resumed['chat_events']) == 1


def test_retry_retains_turns_and_question_before_finishing_all_participants(tmp_path):
    llm = ConversationTrace()
    api, _, base, _ = selected(tmp_path, llm)
    llm.fail_interact_at = 4
    question = {'question': '역할마다 준비 노력과 효과를 비교해주세요.'}
    failed = api.post(base + '/ask', json=question)
    assert failed.status_code == 502
    partial = api.get(base).json()
    assert len(partial['threads']) == 1 and partial['transcript']
    assert api.post(base + '/ask', json={'question': '다른 질문'}).status_code >= 400
    assert api.post(base + '/finish', json={}).status_code >= 400
    resumed = successful(api.post(base + '/ask', json=question))
    assert resumed['transcript'][:len(partial['transcript'])] == partial['transcript']
    assert len(resumed['threads']) == 1
    assert {t['persona_id'] for t in thread_turns(resumed)} == {'p1', 'p2', 'p3'}
    assert len({t['id'] for t in resumed['transcript']}) == len(resumed['transcript'])
    assert sum(e['role'] == 'founder' and e['content'] == question['question'] for e in resumed['chat_events']) == 1
    assert not structural_metrics(Session.model_validate(resumed))['invalid_reply_ids']


def test_report_is_snapshot_and_chat_continues_without_report_call(tmp_path):
    api, llm, base, _ = selected(tmp_path)
    successful(api.post(base + '/ask', json={'question': '현재 대안을 비교해 주세요.'}))
    completed = successful(api.post(base + '/finish', json={}))
    report_calls = sum(r['task'] == 'report' for r in llm.records)
    report = copy.deepcopy(completed['report'])
    closing = [t for t in completed['transcript'] if t['round'] == 'Closing check']
    post = [t for t in completed['transcript'] if t['phase'] == 'post']
    continued = successful(api.post(base + '/ask', json={'question': '새로 확인할 사용 중단 조건은 무엇일까요?'}))
    assert continued['status'] == 'WAITING' and continued['report_stale'] is True
    assert continued['report'] == report
    assert sum(r['task'] == 'report' for r in llm.records) == report_calls
    refreshed = successful(api.post(base + '/finish', json={}))
    assert refreshed['status'] == 'COMPLETE' and refreshed['report_stale'] is False
    assert sum(r['task'] == 'report' for r in llm.records) == report_calls + 1
    assert refreshed['transcript'][:len(completed['transcript'])] == completed['transcript']
    assert [t for t in refreshed['transcript'] if t['round'] == 'Closing check'] == closing
    refreshed_post = [t for t in refreshed['transcript'] if t['phase'] == 'post']
    assert refreshed_post[:len(post)] == post and len(refreshed_post) == len(post) + 3
    assert len({t['id'] for t in refreshed['transcript']}) == len(refreshed['transcript'])
    calls = len(llm.records)
    cached = successful(api.post(base + '/finish', json={}))
    assert cached['report'] == refreshed['report'] and cached['transcript'] == refreshed['transcript']
    assert len(llm.records) == calls


def test_calibration_keeps_its_original_report_revision_after_new_chat(tmp_path):
    api, _, base, _ = selected(tmp_path)
    successful(api.post(base + '/ask', json={'question': '현재 대안과 조건을 비교해 주세요.'}))
    completed = successful(api.post(base + '/finish', json={}))
    annotation = {'dataset_kind': 'synthetic', 'predicted_themes': ['조건'], 'real_themes': ['조건']}
    result = api.post(base + '/calibrate', json=annotation)
    assert result.status_code == 200, result.text
    calibrated = api.get(base).json()
    revision = calibrated['calibration_revision']
    assert revision == completed['report_revision']
    continued = successful(api.post(base + '/ask', json={'question': '사용 중단 조건은 무엇일까요?'}))
    assert continued['calibration_revision'] == revision and continued['report_stale'] is True
    refreshed = successful(api.post(base + '/finish', json={}))
    assert refreshed['report_revision'] > revision
    assert refreshed['calibration_revision'] == revision
    assert refreshed['calibration'] == calibrated['calibration']


def test_report_failure_retry_does_not_repeat_closing_or_private_post(tmp_path):
    llm = ConversationTrace()
    api, _, base, _ = selected(tmp_path, llm)
    successful(api.post(base + '/ask', json={'question': '대안과 전환 조건은?'}))
    llm.fail_report_once = True
    assert api.post(base + '/finish', json={}).status_code == 502
    partial = api.get(base).json()
    assert partial['status'] == 'REPORT'
    assert not any(t['round'] == 'Closing check' for t in partial['transcript'])
    assert sum(t['phase'] == 'post' for t in partial['transcript']) == 3
    resumed = successful(api.post(base + '/finish', json={}))
    assert resumed['status'] == 'COMPLETE'
    assert resumed['transcript'] == partial['transcript']
    assert resumed['error'] is None and resumed['report_stale'] is False


def test_many_report_snapshots_keep_model_prompt_bounded_and_source_unchanged(tmp_path):
    from backend.services import generate_report
    class ReportCapture(LLMClient):
        def __init__(self):
            super().__init__('mock')
            self.report_payload = None

        def call(self, task, payload, schema, **kwargs):
            if task == 'report':
                self.report_payload = copy.deepcopy(payload)
            return super().call(task, payload, schema, **kwargs)

    llm = ReportCapture()
    _, _, _, raw = selected(tmp_path, llm)
    session = Session.model_validate(raw)
    for card in session.cards:
        session.transcript.append(Utterance(id='pre-' + card.id, persona_id=card.id,
            phase='pre', round='Private Pre', question='사전 판단', content='초기 조건 가설'))
    for revision in range(12):
        for card in session.cards:
            session.transcript.append(Utterance(id=f'group-{revision}-{card.id}', persona_id=card.id,
                phase='group', round='Founder Follow-up', question='현재 조건', content=f'{revision} 공개 조건 비교 가설'))
        for card in session.cards:
            session.transcript.append(Utterance(id=f'post-{revision}-{card.id}', persona_id=card.id,
                phase='post', round='Private Post', question='개인 판단', content=f'{revision} 개인 최종 판단 가설'))
    original = session.model_dump(mode='json')['transcript']
    generate_report(session, llm)
    excerpts = llm.report_payload['transcript']
    ids = {t.split('|')[0] for t in excerpts}
    assert len(excerpts) <= 30
    assert {'pre-p1', 'pre-p2', 'pre-p3', 'post-11-p1', 'post-11-p2', 'post-11-p3'} <= ids
    assert not any(id.startswith('post-') and not id.startswith('post-11-') for id in ids)
    assert session.model_dump(mode='json')['transcript'] == original
    assert llm.report_payload['omitted_utterance_count'] == len(original) - len(excerpts)


def test_agent_discards_unseen_private_or_invented_references(tmp_path):
    _, _, _, raw = selected(tmp_path)
    session = Session.model_validate(raw)
    class BadRefs(LLMClient):
        def call(self, *args, **kwargs):
            return InteractionAnswer(content='가설로는 조건을 비교해야 합니다.',
                reply_to='another-person-private', addressed_to='not-a-participant',
                evidence_ids=['invented-source'], reasoning_rule_ids=['invented-rule', 'r1'])

    agent = PersonaAgent(session.cards[0], BadRefs('mock'))
    public = ContextManager()
    public.add({'id': 'visible-peer', 'persona_id': 'p2', 'phase': 'group', 'content': '공개 조건 가설'})
    before = fingerprint(agent.card)
    answer = agent.answer(session.brief, 'group', 'Founder Follow-up', '조건은?', public,
        interaction=True, participants=['p1', 'p2', 'p3'], dialogue_goal='조건은?')
    assert answer.reply_to is None and answer.addressed_to is None
    assert answer.evidence_ids == [] and answer.reasoning_rule_ids == ['r1']
    assert fingerprint(agent.card) == before


def test_context_compaction_preserves_current_parent_root_and_actual_reply_enum():
    import json
    import httpx
    bodies = []
    def handler(request):
        if request.url.path in ('/props', '/apply-template'):
            return httpx.Response(404)
        raw = json.loads(request.content)
        if request.url.path == '/tokenize':
            return httpx.Response(200, json={'tokens': [1] * (len(raw['content']) // 2)})
        bodies.append(raw)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'content': '조건에 따른 가설입니다.', 'reply_to': 'parent',
                'dialogue_act': 'answer', 'addressed_to': None, 'followup_question': ''})}}],
            'usage': {'prompt_tokens': 1000, 'completion_tokens': 60}})

    client = LLMClient('qwen', context_size=6000, transport=httpx.MockTransport(handler))
    parent = {'id': 'parent', 'persona_id': 'p2', 'phase': 'group',
        'content': '예산 상한이 10만원이면 검토할 수 있지만 기존 계약을 중도 해지해야 한다면 보류한다는 가설입니다.'}
    turns = [parent] + [{'id': f'old-{n}', 'persona_id': 'p2', 'phase': 'group',
        'content': '이전 조건을 반복하여 설명하는 오래된 공개 의견 ' * 40} for n in range(9)]
    root = '예산 상한과 중도 해지 비용이 판단을 어떻게 바꾸나요?'
    core = {'identity_context': {'segment': '인터뷰 준비 담당자'},
        'decision_model': {'budget_constraint': '10만원'}}
    payload = {'card': {'id': 'p1', 'immutable_core': core}, 'phase': 'group',
        'round': 'Founder Follow-up', 'question': '동료의 유보 조건에 답해주세요.',
        'dialogue_goal': root, 'required_parent': parent, 'participants': ['p1', 'p2'],
        'group': {'older_summary': '', 'recent': turns}, 'own': {'older_summary': '', 'recent': []}}
    original = copy.deepcopy(payload)
    client.call('interact', payload, InteractionAnswer, max_tokens=360)
    sent = json.loads(bodies[-1]['messages'][1]['content'])
    assert sent['dialogue_goal'] == root and sent['required_parent'] == parent
    assert sent['card']['immutable_core'] == core
    assert client.records[-1]['context_compactions'] > 0
    enum = bodies[-1]['response_format']['json_schema']['schema']['properties']['reply_to']['anyOf'][0]['enum']
    visible = {t['id'] for t in sent['group']['recent']} | {sent['required_parent']['id']}
    assert set(enum) == visible
    assert payload == original


@pytest.mark.parametrize(('role', 'alternative'), [('최종사용자', '창업지원단 무료 상담'), ('UNKNOWN', 'UNKNOWN')])
def test_chat_own_basis_grammar_uses_exact_own_card_constants_first(role, alternative):
    """Metadata constraints and field order are not proof of natural-language faithfulness."""
    import json
    import httpx
    bodies = []
    def handler(request):
        if request.url.path in ('/props', '/apply-template'):
            return httpx.Response(404)
        if request.url.path == '/tokenize':
            return httpx.Response(200, json={'tokens': [1] * 500})
        body = json.loads(request.content)
        bodies.append(body)
        result = {'own_basis': {'role': role, 'expected_alternative': alternative},
            'content': '제 조건에 따른 가설이며 실제 사용이나 선호를 확인한 결과가 아닙니다.',
            'stance': 'conditional', 'reason': '자기 카드의 역할과 대안을 비교하는 조건부 판단',
            'unresolved_issues': ['실제 고객에게 확인할 도입 조건'],
            'reasoning_rule_ids': ['p1:r1'],
            'dialogue_act': 'answer', 'addressed_to': None, 'followup_question': '', 'followup_kind': 'none'}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(result, ensure_ascii=False)}}]})

    client = LLMClient('qwen', transport=httpx.MockTransport(handler))
    payload = {'card': {'id': 'p1', 'immutable_core': {
        'identity_context': {'segment': '인터뷰 준비 예비창업자'},
        'decision_model': {'buying_role': role}, 'problem_context': {'current_alternative': alternative},
        'reasoning_rules': [{'id':'p1:r1','trigger':'새 방법 검토','value':'조건에 맞는 효과','tradeoff':'준비 노력',
            'conditional_choice':'효과가 노력을 넘는다면 검토'}]}},
        'phase': 'group', 'round': 'Founder Follow-up', 'question': '동료 조건과 비교하세요.',
        'conversation_step': 'cross_response', 'dialogue_goal': '준비 노력과 효과는?',
        'participants': ['p1', 'p2'], 'group': {'recent': [], 'older_summary': ''},
        'required_parent': {'id': 'peer', 'persona_id': 'p2', 'phase': 'group',
            'reasoning_rule_ids':['p2:r1'],
            'content': '기관 구매담당으로 기업 컨설팅을 검토하는 조건부 가설입니다.'}}
    original = copy.deepcopy(payload)
    answer = client.call('chat', payload, InteractionAnswer, max_tokens=640)
    body = bodies[-1]
    grammar = body['response_format']['json_schema']['schema']
    assert list(grammar['properties'])[0] == 'own_basis' and grammar['required'][0] == 'own_basis'
    assert {'reason', 'stance', 'unresolved_issues', 'reasoning_rule_ids'} <= set(grammar['required'])
    basis = grammar['properties']['own_basis']
    assert basis['type'] == 'object' and basis['additionalProperties'] is False
    assert set(basis['properties']) == set(basis['required']) == {'role', 'expected_alternative'}
    assert basis['properties']['role']['const'] == role
    assert basis['properties']['expected_alternative']['const'] == alternative
    assert grammar['properties']['reasoning_rule_ids']['items']['enum'] == ['p1:r1']
    layout = json.loads(body['messages'][0]['content'].split('Output field layout: ')[-1])
    assert list(layout)[0] == 'own_basis'
    assert answer.own_basis.role == role and answer.own_basis.expected_alternative == alternative
    assert payload == original


def test_legacy_interaction_and_private_answers_do_not_require_own_basis():
    import json
    import httpx
    from backend.schemas import AgentAnswer
    bodies = []
    def handler(request):
        if request.url.path in ('/props', '/apply-template'):
            return httpx.Response(404)
        if request.url.path == '/tokenize':
            return httpx.Response(200, json={'tokens': [1] * 500})
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': '{"content":"기존 기록의 조건부 답변입니다."}'}}]})

    client = LLMClient('qwen', transport=httpx.MockTransport(handler))
    legacy = client.call('interact', {'participants': ['p1', 'p2']}, InteractionAnswer)
    assert legacy.own_basis is None
    assert 'own_basis' not in bodies[-1]['response_format']['json_schema']['schema']['required']
    assert 'const' not in json.dumps(bodies[-1]['response_format']['json_schema']['schema']['properties']['own_basis'])
    client.call('agent', {'phase': 'pre'}, AgentAnswer)
    assert 'own_basis' not in bodies[-1]['response_format']['json_schema']['schema']['properties']
    assert InteractionAnswer.model_validate({'content': '저장된 기존 답변'}).own_basis is None


def test_chat_payloads_never_include_other_personas_private_card_fields(tmp_path):
    api, trace, base, original = selected(tmp_path, ConversationTrace(ongoing=False))
    session = Session.model_validate(original)
    markers = {c.id: f'PRIVATE_CARD_SYNTHETIC_{c.id}' for c in session.cards}
    for card in session.cards:
        raw = card.immutable_core.model_dump()
        raw['identity_context']['domain_experience'] = markers[card.id]
        card.immutable_core = type(card.immutable_core).model_validate(raw)
    # Simulate already-stored cards; this test concerns isolation, not the builder evidence gate.
    api.app.state.store.put(session)
    before = [fingerprint(c) for c in session.cards]
    result = successful(api.post(base + '/ask', json={'question': '자기 조건을 동료와 비교해주세요.'}))
    import json
    for payload in [p for p in trace.payloads if p['phase'] == 'group']:
        pid = payload['card']['id']
        packed = json.dumps(payload, ensure_ascii=False)
        assert markers[pid] in packed
        assert all(marker not in packed for other, marker in markers.items() if other != pid)
        assert 'presentation' not in payload['card']
    assert [fingerprint(c) for c in Session.model_validate(result).cards] == before


def perspective_fixture(tmp_path, candidates, mode='mock', repeat_in_public=False):
    _, _, _, raw = selected(tmp_path)
    session = Session.model_validate(raw)
    card = session.cards[2]
    card.presentation.display_name = '박시온'
    # Make the synthetic owner/peer roles explicit rather than relying on ranked target order.
    core = card.immutable_core.model_dump()
    core['identity_context']['role'] = '결정자'
    core['decision_model']['buying_role'] = '결정자'
    card.immutable_core = type(card.immutable_core).model_validate(core)
    question = '검증 비용과 현재 대안은 어떤 조건에서 비교할까요?'
    baseline = '가설로는 검증 효과가 준비 노력보다 클 때 제 결정 권한에서 검토할 수 있습니다. 실제 도입은 아직 판단할 수 없습니다.'
    parent = {'id': 'peer-p1', 'persona_id': 'p1', 'phase': 'group', 'speaker_alias': '김하늘',
        'hypothetical_role': '정보제공자', 'expected_alternative': 'UNKNOWN',
        'content': '정보제공자라는 조건에서는 검증 정보를 비교한다는 가설입니다.'}
    class Candidates(LLMClient):
        def __init__(self):
            super().__init__(mode)
            self.payloads = []

        def call(self, task, payload, schema, **kwargs):
            self.payloads.append({'task': task, 'payload': copy.deepcopy(payload), 'options': kwargs})
            content = candidates[min(len(self.payloads)-1, len(candidates)-1)]
            return InteractionAnswer(content=content, stance='conditional', reason='synthetic 비교',
                reasoning_rule_ids=['r1'], dialogue_act='question', addressed_to='p1',
                followup_question='효과를 어떻게 확인할까요?', followup_kind='peer_condition',
                own_basis={'role': card.immutable_core.decision_model.buying_role,
                    'expected_alternative': card.immutable_core.problem_context.current_alternative})

    llm = Candidates()
    agent = PersonaAgent(card, llm)
    agent.context.add({'id': 'baseline-p3', 'persona_id': 'p3', 'phase': 'group', 'round': 'Founder Follow-up',
        'question': question, 'content': baseline, 'stance': 'conditional', 'reasoning_rule_ids': ['r1']})
    public = ContextManager()
    public.add(parent)
    if repeat_in_public:
        public.add({'id': 'repeated', 'persona_id': 'p1', 'phase': 'group', 'content': candidates[0]})
    before = fingerprint(agent.card)
    answer = agent.answer(session.brief, 'group', 'Founder Follow-up', '동료의 조건에 답하세요.', public,
        interaction=True, participants=['p1', 'p2', 'p3'], participant_names={'p1': '김하늘', 'p3': '박시온'},
        dialogue_goal=question, conversation_step='cross_response', required_parent=parent,
        participant_profiles={'p1': {'role': '정보제공자'}, 'p2': {'role': '최종사용자'}, 'p3': {'role': '결정자'}})
    assert fingerprint(agent.card) == before
    assert all('participant_profiles' not in entry['payload'] for entry in llm.payloads)
    return answer, llm, baseline


@pytest.mark.parametrize(('candidate', 'flag'), [
    ('저는 정보제공자입니다. 검증 정보를 비교하는 조건을 따져보겠습니다.', 'persona_identity_mismatch'),
    ('박시온님이 말씀하신 조건을 저는 그대로 따르겠습니다.', 'persona_self_address')])
def test_role_mismatch_or_self_address_preserves_raw_and_independent_view(tmp_path, candidate, flag):
    answer, llm, baseline = perspective_fixture(tmp_path, [candidate])
    assert len(llm.payloads) == 1
    assert answer.generated_content == candidate and flag + '_withheld' in answer.quality_flags
    assert answer.content == baseline and '독립 판단' in answer.reason
    assert answer.dialogue_act == 'answer' and not answer.followup_question and answer.addressed_to is None
    assert answer.followup_kind == 'none' and answer.stance == 'conditional'


def test_role_repair_is_bounded_and_original_candidate_is_kept(tmp_path):
    bad = '저는 정보제공자로서 검증 정보를 비교하겠습니다.'
    fixed = '가설로는 결정자라는 제 조건에서 준비 노력과 검증 효과를 비교하겠습니다.'
    answer, llm, _ = perspective_fixture(tmp_path, [bad, fixed], mode='qwen')
    assert len(llm.payloads) == 2 and all(entry['task'] == 'chat' for entry in llm.payloads)
    assert answer.generated_content == bad and answer.content == fixed
    assert answer.quality_flags == ['persona_identity_mismatch_repaired']
    correction = llm.payloads[1]['payload']['correction_request']
    assert correction['own_role'] == '결정자' and correction['parent_name'] == '김하늘'
    assert correction['candidate'] == bad


def test_repeat_role_and_overclaim_share_one_repair_then_withhold(tmp_path):
    bad = '저는 정보제공자로서 검증 정보를 비교하고 이 도구를 구매하겠습니다.'
    answer, llm, baseline = perspective_fixture(tmp_path, [bad, bad], mode='qwen', repeat_in_public=True)
    assert len(llm.payloads) == 2
    assert answer.generated_content == bad and answer.content == baseline
    assert 'persona_identity_mismatch_withheld' in answer.quality_flags
    assert '구매하겠습니다' not in answer.content and '정보제공자' not in answer.content


@pytest.mark.parametrize('candidate', [
    '김하늘님은 정보제공자 관점을 설명하셨고, 저는 결정자 조건에서 효과와 준비 노력을 비교하겠습니다.',
    '제가 김하늘님의 정보제공자 조건을 이해한 바로는, 실제 효과를 먼저 확인해야 한다는 가설입니다.'
])
def test_valid_peer_role_mentions_are_not_treated_as_self_identity_claims(tmp_path, candidate):
    answer, llm, _ = perspective_fixture(tmp_path, [candidate], mode='qwen')
    assert len(llm.payloads) == 1
    assert answer.content == candidate and answer.generated_content is None
    assert not answer.quality_flags


@pytest.mark.parametrize('bad_reference',['p2:r1','p1:invented'])
def test_owner_qualified_rules_map_back_locally_and_peer_or_invented_rules_are_dropped(tmp_path,bad_reference):
    _, _, _, raw = selected(tmp_path)
    session = Session.model_validate(raw)
    card = session.cards[0]
    original = card.model_dump(mode='json')
    class RuleRefs(LLMClient):
        def __init__(self):
            super().__init__('mock')
            self.payload = None

        def call(self, task, payload, schema, **kwargs):
            self.payload = copy.deepcopy(payload)
            return InteractionAnswer(content='자기 조건에 따른 가설로 비교하겠습니다.',
                reasoning_rule_ids=['p1:r1', bad_reference], dialogue_act='answer')

    llm = RuleRefs()
    agent = PersonaAgent(card, llm)
    answer = agent.answer(session.brief, 'group', 'Founder Follow-up', '조건은?',
        interaction=True, participants=['p1', 'p2'], dialogue_goal='조건은?', conversation_step='cross_response',
        required_parent={'id':'peer','persona_id':'p2','phase':'group','content':'상대 조건 가설',
            'reasoning_rule_ids':['p2:r1']})
    assert answer.reasoning_rule_ids == ['r1']
    assert llm.payload['card']['immutable_core']['reasoning_rules'][0]['id'] == 'p1:r1'
    assert llm.payload['own_decision_frame']['rules'][0]['id'] == 'p1:r1'
    assert agent.card.model_dump(mode='json') == original and card.model_dump(mode='json') == original


def test_public_chat_owned_context_is_bounded_and_excludes_prior_generated_traits(tmp_path):
    _, _, _, raw = selected(tmp_path)
    session = Session.model_validate(raw)
    class Trace(LLMClient):
        def __init__(self):
            super().__init__('mock')
            self.payload = None

        def call(self, task, payload, schema, **kwargs):
            self.payload = copy.deepcopy(payload)
            return super().call(task, payload, schema, **kwargs)

    llm = Trace()
    agent = PersonaAgent(session.cards[0], llm)
    root = '지금 질문의 검토 조건은?'
    for n in range(7):
        agent.context.add({'id':f'old-{n}','persona_id':'p1','phase':'group','question':'이전 질문',
            'content':'이전 자신 의견은 확정된 성격이 아닌 가설입니다. '*20})
    first = {'id':'independent','persona_id':'p1','phase':'group','question':root,
        'content':'현재 질문에 대한 자기 조건의 독립 가설입니다.','stance':'conditional'}
    agent.context.add(first)
    agent.state.reasons = ['GENERATED_REASON_MUST_NOT_BECOME_TRAIT']
    agent.state.unresolved_issues = ['GENERATED_ISSUE_MUST_NOT_BECOME_TRAIT']
    source = copy.deepcopy(agent.context.recent)
    baseline = {'content':'자신의 비공개 사전 가설','stance':'conditional','reason':'초기 가설'}
    answer = agent.answer(session.brief, 'group', 'Founder Follow-up', '동료 조건에 답하세요.',
        interaction=True, participants=['p1','p2'], dialogue_goal=root, conversation_step='cross_response',
        private_baseline=baseline,
        required_parent={'id':'public-peer','persona_id':'p2','phase':'group','content':'동료 공개 조건 가설'})
    payload = llm.payload
    assert len(payload['own']['recent']) == 1 and payload['own']['recent'][0]['id'] == first['id']
    assert len(payload['own']['prior_view_excerpts']) <= 2
    assert all(len(t['content']) <= 120 and t['hypothesis'] is True for t in payload['own']['prior_view_excerpts'])
    assert set(payload['state']) <= {'stance','note'}
    import json
    assert 'GENERATED_REASON_MUST_NOT_BECOME_TRAIT' not in json.dumps(payload,ensure_ascii=False)
    assert 'GENERATED_ISSUE_MUST_NOT_BECOME_TRAIT' not in json.dumps(payload,ensure_ascii=False)
    assert payload['private_baseline'] == baseline and payload['group'] == {'older_summary':'','recent':[]}
    assert agent.context.recent == source
    assert answer.reasoning_rule_ids == ['r1']


def consensus_fixture(tmp_path):
    from backend.schemas import Report, Insight, SECTIONS
    _, _, _, raw = selected(tmp_path)
    session = Session.model_validate(raw)
    for n, card in enumerate(session.cards):
        session.transcript.append(Utterance(id=f'public-{n+1}', persona_id=card.id, phase='group',
            round='Founder Follow-up', question='조건은?', content=f'{card.id}의 조건부 가설'))
    report = Report(sections={name:[Insight(text=name+' 개별 가설', utterance_ids=['public-1'])] for name in SECTIONS})
    return session, report


def test_universal_agreement_missing_persona_is_withheld_and_audit_is_idempotent(tmp_path):
    from backend.services import guard_report_consensus
    session, report = consensus_fixture(tmp_path)
    row = report.sections['Agreement'][0]
    row.text = '모든 참여자가 도입의 효과가 확인되면 사용하겠다는 데 동의했습니다.'
    row.utterance_ids = ['public-2','public-3']
    row.confidence = 'high'
    original = row.model_dump(mode='json')
    source = copy.deepcopy(session.model_dump(mode='json')['transcript'])
    guarded = guard_report_consensus(session, report)
    assert guarded is report and row.confidence == 'low'
    assert '인용 근거가 부족' in row.text and row.utterance_ids == original['utterance_ids']
    audits = session.dialogue_runtime['report_claim_audits']
    assert len(audits) == 1 and audits[0]['original_claim'] == original
    assert audits[0]['missing_persona_ids'] == ['p1'] and audits[0]['public_revision'] == 3
    assert audits[0]['semantic_consensus_verified'] is False
    notice = report.notice
    guard_report_consensus(session, report)
    assert len(audits) == 1 and report.notice == notice
    assert session.model_dump(mode='json')['transcript'] == source


def test_universal_coverage_and_individual_subset_are_not_semantically_rejudged(tmp_path):
    from backend.services import guard_report_consensus
    from backend.schemas import Insight
    session, report = consensus_fixture(tmp_path)
    report.sections['Agreement'] = [
        Insight(text='All participants agree to compare the conditions.',
            utterance_ids=['public-1','public-2','public-3'],confidence='medium'),
        Insight(text='김하늘님은 효과가 확인되면 검토할 수 있다는 개별 가설을 제시했습니다.',
            utterance_ids=['public-1'],confidence='low')]
    original = report.model_dump(mode='json')
    guard_report_consensus(session, report)
    assert report.model_dump(mode='json') == original
    assert not session.dialogue_runtime.get('report_claim_audits')
    # Citation coverage passes this narrow guard; it does not prove semantic agreement.


def test_cached_finish_applies_consensus_guard_and_persists_without_model_call(tmp_path):
    api, llm, base, _ = selected(tmp_path)
    successful(api.post(base+'/ask',json={'question':'자기 조건을 비교해주세요.'}))
    completed = successful(api.post(base+'/finish',json={}))
    session = api.app.state.store.get(completed['id'])
    row = session.report.sections['Agreement'][0]
    row.text = 'Everyone agrees that the adoption conditions have been met.'
    row.confidence = 'high'
    row.utterance_ids = [next(t.id for t in session.transcript if t.phase=='group' and t.persona_id==pid) for pid in ('p2','p3')]
    original = row.model_dump(mode='json')
    api.app.state.store.put(session)
    before = len(llm.records)
    cached = successful(api.post(base+'/finish',json={}))
    assert len(llm.records) == before
    assert cached['transcript'] == completed['transcript']
    assert cached['report']['sections']['Agreement'][0]['confidence'] == 'low'
    stored = api.get(base).json()
    audits = stored['dialogue_runtime']['report_claim_audits']
    assert len(audits) == 1 and audits[0]['original_claim'] == original
    assert audits[0]['missing_persona_ids'] == ['p1']
    successful(api.post(base+'/finish',json={}))
    assert len(llm.records) == before
    assert len(api.get(base).json()['dialogue_runtime']['report_claim_audits']) == 1
