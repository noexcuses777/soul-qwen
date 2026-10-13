"""Synthetic functional checks of selective depth, not evidence of Qwen quality."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.context import fingerprint
from backend.llm import LLMClient, LLMError
from backend.schemas import ConversationThread, InteractionAnswer, Session, Utterance


class DepthTrace(LLMClient):
    """Distinct conditional arguments exercise real controller/context code."""
    TEXT = {
        'contribution': '가설로는 준비 부담이 줄어드는 조건에서 검토할 수 있습니다. 효과가 불분명하다면 기존 대안을 유지하는 선택도 가능합니다.',
        'cross_response': '동료의 편의성 조건은 제 상황과 같다고 단정할 수 없습니다. 결정 권한에 따라 사용 편의보다 설명 가능한 판단 근거를 먼저 확인할 수 있습니다.',
        'clarification': '가설로는 새로운 과정이 기존 업무를 대체하는 경우와 추가되는 경우를 구분하겠습니다. 추가 업무라면 편의성만으로 선택을 바꾸기 어렵습니다.',
        'refinement': '동료의 지적을 반영해 처음의 편의성 판단을 좁히겠습니다. 준비가 쉬워지는 것과 판단이 정확해지는 것은 다르므로, 기존 대안과 비교할 근거가 생기는 조건을 별도로 보겠습니다.',
        'decision_probe': '검증 자료를 만드는 과정 자체가 부담이라면 사용을 보류할 수 있습니다. 실제 고객에게는 현재 판단 과정을 설명하게 하고, 새 도구가 어느 과정을 줄였는지 확인하는 질문을 하겠습니다.',
    }

    def __init__(self, external=False, repeating=False, directed=False):
        super().__init__('mock')
        self.payloads = []
        self.calls = 0
        self.fail_at = None
        self.external = external
        self.repeating = repeating
        self.directed = directed

    def call(self, task, payload, schema, **kwargs):
        if task != 'chat':
            return super().call(task, payload, schema, **kwargs)
        self.calls += 1
        self.payloads.append(copy.deepcopy(payload))
        if self.calls == self.fail_at:
            raise LLMError('synthetic late interruption')
        step = payload['conversation_step']
        pid = payload['card']['id']
        issue = '판단 근거를 확인하는 과정의 부담'
        text = self.TEXT['contribution'] if self.repeating else self.TEXT[step]
        # This is an artificial role-specific conditional view, never real customer data.
        text = payload['own_decision_frame']['hypothetical_role'] + ' 조건에서 ' + text
        question = ''
        addressed = None
        kind = 'real_world_check' if self.external else 'none'
        if self.directed and step == 'contribution' and pid == 'p1':
            question = '새 과정이 기존 업무를 대체해야 한다는 조건을 어떻게 해석하시나요?'
            addressed = 'p2'
            kind = 'clarification'
        return InteractionAnswer(
            content=text, stance='conditional', reason='자기 역할의 준비 부담과 판단 근거를 구분하는 synthetic 조건',
            reasoning_rule_ids=[pid + ':r1'], unresolved_issues=[issue],
            dialogue_act='question' if question else 'answer', addressed_to=addressed,
            followup_question=question, followup_kind=kind,
            own_basis={'role': payload['own_decision_frame']['hypothetical_role'],
                       'expected_alternative': payload['own_decision_frame']['expected_alternative']})


def selected(tmp_path, llm=None, n=3):
    llm = llm or DepthTrace()
    api = TestClient(create_app(str(tmp_path / 'depth.db'), llm))
    response = api.post('/api/sessions', json={'q1': '창업 아이디어 인터뷰 준비 도구', 'q5': 'IT'})
    assert response.status_code == 200, response.text
    base = '/api/sessions/' + response.json()['id']
    response = api.post(base + '/select', json={'target_ids': [f't{i+1}' for i in range(n)]})
    assert response.status_code == 200, response.text
    return api, llm, base, response.json()


def ask(api, base, question='현재 대안과 도입 조건을 비교해주세요.', **kwargs):
    response = api.post(base + '/ask', json={'question': question, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def active_turns(session):
    ids = set(session['threads'][-1]['utterance_ids'])
    return [t for t in session['transcript'] if t['id'] in ids]


def test_grounded_neutral_views_expand_beyond_six_with_a_b_a_return(tmp_path):
    api, trace, base, original = selected(tmp_path)
    result = ask(api, base)
    turns = active_turns(result)
    assert 6 < len(turns) <= 15
    assert result['protocol_version'] == '6'
    assert result['status'] == 'WAITING' and result['report'] is None
    assert [p['conversation_step'] for p in trace.payloads[:3]] == ['contribution'] * 3
    assert all(t['stance'] == 'conditional' and t['dialogue_act'] == 'answer' for t in turns)
    assert {t['persona_id'] for t in turns} == {'p1', 'p2', 'p3'}
    mapping = {t['id']: t for t in turns}
    order = {t['id']: i for i, t in enumerate(turns)}
    runtime = result['dialogue_runtime']['followup']
    assert runtime['refinement_turns'] and runtime['probed']
    for turn in turns:
        if turn['reply_to']:
            parent = mapping[turn['reply_to']]
            assert order[parent['id']] < order[turn['id']]
            assert parent['persona_id'] != turn['persona_id']
    for uid in runtime['refinement_turns']:
        returned = mapping[uid]
        cross = mapping[returned['reply_to']]
        first = mapping[cross['reply_to']]
        assert cross['id'] in runtime['cross_turns']
        assert first['persona_id'] == returned['persona_id'] != cross['persona_id']
    assert [fingerprint(c) for c in Session.model_validate(result).cards] == [
        fingerprint(c) for c in Session.model_validate(original).cards]


def test_directed_clarification_has_priority_after_independent_views(tmp_path):
    api, trace, base, _ = selected(tmp_path, DepthTrace(directed=True))
    result = ask(api, base)
    assert [p['conversation_step'] for p in trace.payloads[:3]] == ['contribution'] * 3
    next_payload = trace.payloads[3]
    assert next_payload['conversation_step'] == 'clarification'
    assert next_payload['card']['id'] == 'p2'
    assert next_payload['required_parent']['persona_id'] == 'p1'
    parent = next(t for t in active_turns(result) if t['id'] == next_payload['required_parent']['id'])
    assert parent['followup_question'] == next_payload['question']


def test_all_unknown_conditions_stop_without_manufactured_depth(tmp_path):
    api, trace, base, original = selected(tmp_path)
    session = Session.model_validate(original)
    for card in session.cards:
        raw = card.immutable_core.model_dump()
        raw['reasoning_rules'] = []
        raw['identity_context']['use_context'] = 'UNKNOWN'
        raw['decision_model']['buying_role'] = 'UNKNOWN'
        raw['problem_context']['current_alternative'] = 'UNKNOWN'
        card.immutable_core = type(card.immutable_core).model_validate(raw)
    api.app.state.store.put(session)
    result = ask(api, base)
    assert len(active_turns(result)) == 3
    assert {p['conversation_step'] for p in trace.payloads} == {'contribution'}
    assert result['threads'][-1]['stop_reason'] == 'no_grounded_expansion'


def test_external_checks_remain_for_humans_without_peer_data_invention(tmp_path):
    api, trace, base, _ = selected(tmp_path, DepthTrace(external=True))
    result = ask(api, base)
    assert len(active_turns(result)) <= 9
    assert not any(p['conversation_step'] in ('clarification', 'decision_probe') for p in trace.payloads)
    assert result['threads'][-1]['stop_reason'] == 'real_world_checks_remaining'
    assert result['threads'][-1]['remaining_issues']
    assert all(not t['followup_question'] for t in active_turns(result))


def test_repeated_views_do_not_trigger_refinement_or_probes(tmp_path):
    api, trace, base, _ = selected(tmp_path, DepthTrace(repeating=True))
    result = ask(api, base)
    assert len(active_turns(result)) == 6
    assert not any(p['conversation_step'] in ('refinement', 'decision_probe') for p in trace.payloads)
    assert result['dialogue_runtime']['followup']['done'] is True


@pytest.mark.parametrize('interaction', ['auto', 'interactive', 'direct'])
def test_single_persona_can_deepen_without_self_parent_and_direct_stays_one(tmp_path, interaction):
    api, trace, base, _ = selected(tmp_path, n=1)
    result = ask(api, base, interaction=interaction)
    turns = active_turns(result)
    assert len(turns) == (1 if interaction == 'direct' else 2)
    assert all(not t['reply_to'] for t in turns)
    assert all('required_parent' not in p for p in trace.payloads)
    if interaction != 'direct':
        assert trace.payloads[1]['conversation_step'] == 'decision_probe'
        assert trace.payloads[1]['own']['recent'][0]['id'] == turns[0]['id']


def test_late_failure_resumes_same_action_and_obeys_persisted_budget(tmp_path):
    trace = DepthTrace()
    api, _, base, _ = selected(tmp_path, trace)
    question = {'question': '현재 대안과 도입 조건을 비교해주세요.'}
    trace.fail_at = 8
    response = api.post(base + '/ask', json=question)
    assert response.status_code == 502
    partial = api.get(base).json()
    assert len(active_turns(partial)) == 7
    assert partial['dialogue_runtime']['followup']['budget'] == 15
    failed_payload = copy.deepcopy(trace.payloads[-1])
    model = Session.model_validate(partial)
    # Persisted budget can come from an earlier protocol/configuration. Resume must not
    # silently recompute and exceed it after the server is reloaded.
    model.dialogue_runtime['followup']['budget'] = 8
    api.app.state.store.put(model)
    resumed = ask(api, base, **question)
    assert trace.payloads[8]['question'] == failed_payload['question']
    assert trace.payloads[8]['conversation_step'] == failed_payload['conversation_step']
    assert trace.payloads[8]['card']['id'] == failed_payload['card']['id']
    assert resumed['transcript'][:len(partial['transcript'])] == partial['transcript']
    assert len(resumed['threads']) == 1 and len(active_turns(resumed)) == 8
    assert resumed['dialogue_runtime']['followup']['budget'] == 8
    assert resumed['threads'][-1]['stop_reason'] == 'response_budget'
    assert len({t['id'] for t in resumed['transcript']}) == len(resumed['transcript'])
    assert sum(e['role'] == 'founder' for e in resumed['chat_events']) == 1
    assert sum(t['phase'] == 'pre' for t in resumed['transcript']) == 3


def test_deeper_threads_keep_root_own_history_and_private_context_separate(tmp_path):
    api, trace, base, _ = selected(tmp_path)
    first = ask(api, base, '도입 조건을 비교해주세요.')
    trace.payloads = []
    root = '검증 자료를 준비하는 부담은 어떤 조건에서 달라지나요?'
    second = ask(api, base, root)
    mapping = {t['id']: t for t in second['transcript']}
    thread_ids = set(second['threads'][-1]['utterance_ids'])
    for payload in trace.payloads:
        pid = payload['card']['id']
        assert payload['dialogue_goal'] == root
        assert payload['group'] == {'older_summary': '', 'recent': []}
        assert len(payload['own']['recent']) <= 2
        assert len(payload['own']['prior_view_excerpts']) <= 2
        assert all(mapping[t['id']]['persona_id'] == pid and mapping[t['id']]['phase'] == 'group'
                   and t['id'] in thread_ids for t in payload['own']['recent'])
        assert all(mapping[t['id']]['persona_id'] == pid and mapping[t['id']]['phase'] == 'group'
                   and t['hypothesis'] for t in payload['own']['prior_view_excerpts'])
        pre = next(t for t in second['transcript'] if t['phase'] == 'pre' and t['persona_id'] == pid)
        assert payload['private_baseline']['content'] == pre['content']
        if 'required_parent' in payload:
            parent = payload['required_parent']
            assert parent['id'] in thread_ids and parent['phase'] == 'group'
            assert parent['persona_id'] != pid
    assert second['transcript'][:len(first['transcript'])] == first['transcript']


@pytest.mark.parametrize('latest_kind', ['close', 'real_world_check'])
def test_latest_boundary_does_not_resurrect_older_unresolved_condition(tmp_path, latest_kind):
    from backend.guided import GuidedConversation
    from backend.orchestrator import Orchestrator

    _, llm, _, original = selected(tmp_path, n=2)
    session = Session.model_validate(original)
    question = '도입 조건은 무엇인가요?'
    session.transcript = [
        Utterance(id='u1', persona_id='p1', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='가설로는 준비 부담이 줄어드는 조건을 검토하겠습니다.',
                  reason='자기 역할에서 판단할 준비 조건', unresolved_issues=['준비 과정의 부담']),
        Utterance(id='u2', persona_id='p2', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='더 추론할 근거가 없어 이 판단을 마치겠습니다.',
                  reason='확인 가능한 근거의 경계', dialogue_act='close'),
        Utterance(id='u3', persona_id='p1', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='이후 판단에는 실제 고객의 업무 관찰이 필요하며 현재 카드로 더 알 수 없습니다.',
                  reason='가상 판단으로 확인할 수 없는 외부 자료의 경계',
                  dialogue_act='close' if latest_kind == 'close' else 'answer',
                  followup_kind='none' if latest_kind == 'close' else 'real_world_check',
                  unresolved_issues=[] if latest_kind == 'close' else ['실제 고객의 업무 관찰']),
    ]
    thread = ConversationThread(id='th1', question=question, utterance_ids=['u1', 'u2', 'u3'])
    session.threads = [thread]
    runtime = {'scope': ['p1', 'p2'], 'interaction': 'auto', 'contributed': ['p1', 'p2'],
               'crossed': ['p1', 'p2'], 'handled_requests': [], 'cross_turns': [],
               'refined': [], 'probed': [], 'refinement_turns': []}
    controller = GuidedConversation(llm, Orchestrator(llm).controller)
    controller.restore(session)
    controller.thread_context(thread)
    assert controller.next_action(runtime, thread) is None
    # The older condition stays available for audit; stopping must not erase history.
    assert session.transcript[0].unresolved_issues == ['준비 과정의 부담']


@pytest.mark.parametrize('latest_withheld', [False, True])
def test_generic_peer_uses_latest_corrected_view_without_resurrecting_old_disagreement(tmp_path, latest_withheld):
    from backend.guided import GuidedConversation
    from backend.orchestrator import Orchestrator

    _, llm, _, original = selected(tmp_path, n=2)
    session = Session.model_validate(original)
    question = '새 대안을 검토할 조건은 무엇인가요?'
    session.transcript = [
        Utterance(id='u1', persona_id='p1', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='가설로는 조건에 따라 새 대안을 검토할 수 있습니다.',
                  stance='conditional', reason='조건에 따른 검토'),
        Utterance(id='u2', persona_id='p2', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='준비 부담이 커지는 조건이라면 검토를 보류하겠습니다.',
                  stance='negative', reason='준비 부담에 대한 이전 조건부 판단'),
        Utterance(id='u3', persona_id='p2', phase='group', round='Founder Follow-up',
                  question=question, thread_id='th1', content='앞선 판단을 수정합니다. 기존 과정을 대체한다면 부담이 달라지므로 조건을 나누어 검토하겠습니다.',
                  stance='conditional', reason='기존 과정을 대체하는 경우를 반영한 수정',
                  quality_flags=['unsupported_quantity_withheld'] if latest_withheld else []),
    ]
    thread = ConversationThread(id='th1', question=question, utterance_ids=['u1', 'u2', 'u3'])
    session.threads = [thread]
    controller = GuidedConversation(llm, Orchestrator(llm).controller)
    controller.restore(session)
    controller.agents['p1'].state.stance = 'conditional'
    parent = controller.peer('p1', thread)
    # An earlier contrary stance cannot outrank the speaker's corrected current view.
    # Withholding that current view must not restore the superseded contrary one either.
    assert parent is None if latest_withheld else parent.id == 'u3'
