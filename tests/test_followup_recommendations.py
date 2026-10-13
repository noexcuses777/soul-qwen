"""Synthetic checks of grounded next-question control, not Qwen semantic quality."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.context import fingerprint
from backend.llm import LLMClient, LLMError
from backend.schemas import ConversationThread, Session, Utterance


QUESTION = '기관 담당자가 리포트를 검토할 때 어떤 근거가 필요할까요?'
NEXT = '팀이 직접 수정한 리포트와 자동 생성 리포트는 어떤 승인 기준으로 구분하면 좋을까요?'
ISSUE = '자동 생성 리포트를 승인하는 조건'
PRIVATE_SENTINEL = '공유하면 안 되는 개인의 비공개 사전 응답'


class RecommendationTrace(LLMClient):
    """Serve planned synthetic recommendations while exercising API persistence."""
    def __init__(self, plans=None, reviews=None):
        super().__init__('mock')
        self.plans = list(plans or [])
        self.reviews = list(reviews or [])
        self.payloads = []
        self.fail_once = False

    def call(self, task, payload, schema, **kwargs):
        if task not in ('followup_plan', 'followup_review'):
            return super().call(task, payload, schema, **kwargs)
        self.payloads.append({'task': task, 'payload': copy.deepcopy(payload)})
        if self.fail_once:
            self.fail_once = False
            raise LLMError('synthetic recommendation interruption')
        responses = self.plans if task == 'followup_plan' else self.reviews
        assert responses, 'unexpected extra ' + task + ' model call'
        return schema.model_validate(responses.pop(0))


def selected(tmp_path, llm=None):
    llm = llm or RecommendationTrace()
    api = TestClient(create_app(str(tmp_path / 'recommendations.db'), llm))
    created = api.post('/api/sessions', json={'q1': '창업팀의 고객 인터뷰 준비 도구', 'q5': 'IT'})
    assert created.status_code == 200, created.text
    base = '/api/sessions/' + created.json()['id']
    selection = api.post(base + '/select', json={'target_ids': ['t1', 't2', 't3']})
    assert selection.status_code == 200, selection.text
    session = Session.model_validate(selection.json())
    session.status = 'WAITING'
    session.lounge_mode = 'guided'
    session.protocol_version = '6'
    for card in session.cards:
        card.immutable_core.decision_model.adoption_barrier = '리포트의 검토 과정과 승인 책임 배분'
    session.transcript = [
        Utterance(id='private-pre', persona_id='p1', phase='pre', round='Private Pre',
                  question='독립적인 생각은?', content=PRIVATE_SENTINEL),
        Utterance(id='u1', persona_id='p1', phase='group', round='Founder Follow-up',
                  question=QUESTION, thread_id='th1', content='기관 도입의 가설로 리포트 승인 과정을 구분하고 싶습니다.',
                  reason='리포트를 승인할 때 필요한 설명 가능한 근거', unresolved_issues=[ISSUE]),
        Utterance(id='u2', persona_id='p2', phase='group', round='Founder Follow-up',
                  question=QUESTION, thread_id='th1', content='자동 생성 리포트는 편리해도 팀이 직접 수정하는 승인 과정이 필요할 수 있습니다.',
                  reason='자동 생성과 팀 수정 과정의 차이', unresolved_issues=[ISSUE]),
        Utterance(id='private-post', persona_id='p2', phase='post', round='Private Post',
                  question='사적인 최종 판단은?', content=PRIVATE_SENTINEL + ' 최종'),
    ]
    session.threads = [ConversationThread(id='th1', question=QUESTION, utterance_ids=['u1', 'u2'],
                                        status='returned_to_user', remaining_issues=[ISSUE],
                                        stop_reason='useful_exchange_complete')]
    session.chat_events = [{'id': 'e1', 'role': 'founder', 'content': QUESTION, 'thread_id': 'th1'}]
    session.dialogue_runtime['followup'] = {'done': True, 'thread_id': 'th1'}
    api.app.state.store.put(session)
    return api, llm, base, session


def recommend(api, base):
    response = api.post(base + '/next-question', json={})
    assert response.status_code == 200, response.text
    return response.json()


def new_revision(api, original, question, issue=ISSUE):
    session = api.app.state.store.get(original.id)
    session.transcript.append(Utterance(id='u3', persona_id='p3', phase='group', round='Founder Follow-up',
        question=question, thread_id='th2', content='팀 수정 과정을 거친 뒤에도 검토 책임의 배분이 달라질 수 있습니다.',
        reason='승인 책임을 나누는 조건', unresolved_issues=[issue]))
    session.threads.append(ConversationThread(id='th2', question=question, utterance_ids=['u3'],
        status='returned_to_user', remaining_issues=[issue]))
    session.chat_events.append({'id': 'e2', 'role': 'founder', 'content': question, 'thread_id': 'th2'})
    session.dialogue_runtime['followup'] = {'done': True, 'thread_id': 'th2'}
    api.app.state.store.put(session)
    return session


def plan(question=NEXT, source='u2', **candidate_changes):
    candidate = {'question': question, 'why': '자동 생성과 팀 수정 과정의 승인 기준 차이를 좁힙니다.',
                 'issue': ISSUE, 'angle': '승인 책임과 검토 기준',
                 'new_condition': '팀이 직접 수정하는 과정이 있는 경우',
                 'source_utterance_ids': [source], **candidate_changes}
    return {'candidates': [candidate], 'missing_information': [], 'evidence_question': '',
            'why': '공개 대화에서 아직 비교하지 않은 승인 조건을 확인합니다.'}


def review(novel=True, answerable=True):
    return {'reviews': [{'index': 0, 'novel': novel, 'answerable': answerable,
                         'why': '이미 다룬 조건의 반복입니다.' if not novel else '공개 발화의 조건에서 비교 가능합니다.'}]}


def test_grounded_recommendation_is_persisted_and_cached_without_extra_model_call(tmp_path):
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan()], [review()]))
    first = recommend(api, base)
    assert first['status'] == 'discussion' and first['question'] == NEXT
    assert first['source_utterance_ids'] == ['u2'] and first['id'] and first['why']
    assert isinstance(first['revision'], int)
    second = recommend(api, base)
    assert second == first
    assert [p['task'] for p in trace.payloads] == ['followup_plan', 'followup_review']
    persisted = api.app.state.store.get(original.id)
    assert persisted.dialogue_runtime['next_question_cache']['recommendation']['id'] == first['id']
    assert len(persisted.dialogue_runtime['question_recommendation_history']) == 1


@pytest.mark.parametrize('candidate', [QUESTION, '  ' + QUESTION + '  ', QUESTION.replace('?', '？')])
def test_already_asked_question_is_not_offered_again(tmp_path, candidate):
    api, _, base, _ = selected(tmp_path, RecommendationTrace([plan(candidate)], [review()]))
    result = recommend(api, base)
    assert result['status'] != 'discussion'
    assert result['question'] != candidate


def test_semantic_paraphrase_of_asked_question_is_rejected_by_review(tmp_path):
    paraphrase = '리포트를 승인하는 기관 실무자는 어떤 증거를 먼저 살펴야 할까요?'
    api, trace, base, _ = selected(tmp_path, RecommendationTrace([plan(paraphrase)], [review(novel=False)]))
    result = recommend(api, base)
    assert result['status'] != 'discussion' and result['question'] != paraphrase
    review_payload = next(p['payload'] for p in trace.payloads if p['task'] == 'followup_review')
    assert QUESTION in json.dumps(review_payload, ensure_ascii=False)


@pytest.mark.parametrize('paraphrase', [False, True])
def test_previous_offer_is_rejected_even_if_user_asked_a_different_question(tmp_path, paraphrase):
    repeated = '자동 리포트와 팀이 수정한 리포트의 승인 조건은 어떻게 달라야 할까요?' if paraphrase else NEXT
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan(), plan(repeated, source='u3')],
        [review(), review(novel=not paraphrase)]))
    first = recommend(api, base)
    assert first['status'] == 'discussion'
    new_revision(api, original, '검토 담당자가 바뀌면 책임은 어떻게 나누나요?')
    second = recommend(api, base)
    assert second['revision'] > first['revision']
    assert second['status'] != 'discussion' and second['question'] != repeated
    payload = next(p['payload'] for p in reversed(trace.payloads) if p['task'] == 'followup_plan')
    assert NEXT in json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize('issue', ['타깃 추천의 실제 정확도', '다중 페르소나 대화 시나리오의 실제 유용성'])
def test_external_accuracy_and_usefulness_require_real_evidence(tmp_path, issue):
    evidence_question = issue + '를 검증하려면 실제 사용자와 어떤 비교 결과를 수집해야 하나요?'
    raw = {'candidates': [], 'missing_information': [issue + '를 확인한 실제 평가 자료'],
           'evidence_question': evidence_question, 'why': '가상 페르소나 대화로 실제 성능을 확인할 수 없습니다.'}
    api, trace, base, original = selected(tmp_path, RecommendationTrace([raw]))
    session = original.model_copy(deep=True)
    for turn in session.transcript:
        if turn.phase == 'group':
            turn.content = issue + '는 실제 평가 자료가 없어서 확인할 수 없습니다.'
            turn.unresolved_issues = [issue]
            turn.followup_kind = 'real_world_check'
    session.threads[-1].remaining_issues = [issue]
    session.threads[-1].stop_reason = 'real_world_checks_remaining'
    api.app.state.store.put(session)
    result = recommend(api, base)
    assert result['status'] == 'needs_evidence'
    assert result['missing_information'] and result['question'] == evidence_question
    assert all(p['task'] != 'followup_review' for p in trace.payloads)


def test_observed_qwen_meta_request_is_discarded_while_distinct_observations_remain(tmp_path):
    # Shape observed in a real Qwen smoke run; replay checks control behavior only.
    observations = ['실제 사용자가 추천 타깃을 선택하거나 제외한 이유',
                    '실제 인터뷰 질문을 준비하고 수정하는 과정의 관찰 기록']
    raw = {'candidates': [], 'missing_information': [observations[0], '  ' + observations[0] + '  ',
            observations[1], '구체적인 방법이나 기준'],
           'evidence_question': '구체적인 방법이나 기준을 알려주세요.',
           'why': '타깃 추천의 실제 정확도와 대화의 유용성을 확인하려면 실제 사용자 관찰이 필요합니다.'}
    api, trace, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'needs_evidence'
    assert result['question'] == ''
    assert result['missing_information'] == observations
    assert all(row['task'] != 'followup_review' for row in trace.payloads)


def test_specific_real_customer_interview_question_is_retained_without_fabrication(tmp_path):
    question = '최근 인터뷰 대상을 고를 때 SOUL이 추천한 타깃 중 누구를 제외했고, 어떤 이유로 제외했나요?'
    observation = '실제 창업자가 추천 타깃을 선택하거나 제외한 이유'
    raw = {'candidates': [], 'missing_information': [observation], 'evidence_question': question,
           'why': '추천 타깃의 적합성은 실제 사용자의 선택 이유를 확인해야 합니다.'}
    api, _, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'needs_evidence'
    assert result['question'] == question and result['missing_information'] == [observation]


def test_evidence_requirements_do_not_preserve_unsupported_numeric_claims(tmp_path):
    observation = '실제 사용자의 타깃 선택 이유를 기록한 인터뷰 자료'
    raw = {'candidates': [], 'missing_information': ['추천 정확도가 95%라는 검증 결과', observation],
           'evidence_question': '추천 정확도가 95%라면 실제 사용자의 선택은 어떻게 달라졌나요?',
           'why': '추천 결과의 실제 적합성은 사용자 관찰이 필요합니다.'}
    api, _, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'needs_evidence' and result['question'] == ''
    assert result['missing_information'] == [observation]


def test_vague_method_request_alone_is_not_a_real_evidence_requirement(tmp_path):
    raw = {'candidates': [], 'missing_information': ['구체적인 방법이나 기준'],
           'evidence_question': '구체적인 방법이나 기준을 알려주세요.',
           'why': '추가 조건이 구체적으로 제공되지 않았습니다.'}
    api, _, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'no_new_question'
    assert result['question'] == '' and result['missing_information'] == []


@pytest.mark.parametrize('delivery', ['candidate', 'evidence'])
def test_previously_generated_peer_question_is_not_reoffered(tmp_path, delivery):
    observation = '실제 사용자가 자동 리포트를 승인하거나 수정한 이유'
    raw = plan() if delivery == 'candidate' else {
        'candidates': [], 'missing_information': [observation], 'evidence_question': NEXT,
        'why': '승인 기준은 실제 사용자의 검토 이유를 관찰해야 합니다.'}
    api, trace, base, original = selected(tmp_path, RecommendationTrace([raw], [review()]))
    original.transcript[1].followup_question = NEXT
    original.transcript[1].followup_kind = 'clarification'
    api.app.state.store.put(original)
    result = recommend(api, base)
    assert result['status'] == ('no_new_question' if delivery == 'candidate' else 'needs_evidence')
    assert result['question'] == ''
    assert all(row['task'] != 'followup_review' for row in trace.payloads)
    assert NEXT in [item['question'] for item in trace.payloads[0]['payload']['previous_questions_and_offers']]
    if delivery == 'evidence':
        assert result['missing_information'] == [observation]


@pytest.mark.parametrize('why', [
    '최근 추천 타깃을 제외한 이유는 무엇인가요?',
    '타깃 추천을 평가하려면 어떤 자료를 확인해야 하나요?',
])
def test_needs_evidence_explanation_is_not_a_repeated_or_different_question(tmp_path, why):
    question = '최근 추천 타깃을 제외한 이유는 무엇인가요?'
    observation = '실제 사용자가 추천 타깃을 제외한 이유'
    raw = {'candidates': [], 'missing_information': [observation],
           'evidence_question': question, 'why': why}
    api, _, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'needs_evidence' and result['question'] == question
    assert result['why'] != question and not result['why'].endswith(('?', '？'))
    assert observation in result['why']


def test_different_grounded_issue_produces_a_new_question_after_new_turns(tmp_path):
    followup = '검토 담당자가 바뀌었을 때 팀의 수정 이력을 어떤 방식으로 넘기면 좋을까요?'
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan(), plan(followup, source='u3',
        issue='검토 책임의 인계', angle='수정 이력의 인계', new_condition='검토 책임의 배분이 달라지는 경우')],
        [review(), review()]))
    first = recommend(api, base)
    new_revision(api, original, NEXT, issue='검토 책임의 인계')
    second = recommend(api, base)
    assert second['status'] == 'discussion' and second['question'] == followup
    assert second['question'] != first['question'] and second['id'] != first['id']
    assert second['revision'] > first['revision'] and second['source_utterance_ids'] == ['u3']
    assert [p['task'] for p in trace.payloads].count('followup_plan') == 2


def test_planner_and_reviewer_only_see_attributed_public_excerpts(tmp_path):
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan()], [review()]))
    recommend(api, base)
    for row in trace.payloads:
        encoded = json.dumps(row['payload'], ensure_ascii=False)
        assert PRIVATE_SENTINEL not in encoded
        assert 'private-pre' not in encoded and 'private-post' not in encoded
        assert 'u2' in encoded
    assert fingerprint(api.app.state.store.get(original.id).cards[0]) == fingerprint(original.cards[0])


@pytest.mark.parametrize('source', ['not-a-real-turn', 'private-pre', 'private-post'])
def test_invented_or_private_source_is_rejected(tmp_path, source):
    api, _, base, _ = selected(tmp_path, RecommendationTrace([plan(source=source)], [review()]))
    result = recommend(api, base)
    assert result['status'] != 'discussion'
    assert source not in result['source_utterance_ids']


def test_recommendation_does_not_change_transcript_cards_or_report_snapshot(tmp_path):
    from backend.schemas import Report, SECTIONS
    api, _, base, original = selected(tmp_path, RecommendationTrace([plan()], [review()]))
    original.report = Report(sections={section: [] for section in SECTIONS})
    original.report_revision = 2
    original.report_stale = False
    original.status = 'COMPLETE'
    api.app.state.store.put(original)
    before = original.model_dump(mode='json')
    recommend(api, base)
    after = api.app.state.store.get(original.id).model_dump(mode='json')
    for key in ('transcript', 'cards', 'report', 'report_revision', 'report_stale', 'states', 'threads',
                'chat_events', 'status', 'state_history'):
        assert after[key] == before[key], key


def test_stale_revision_does_not_offer_question_for_changed_conversation(tmp_path):
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan()], [review()]))
    first = recommend(api, base)
    new_revision(api, original, NEXT)
    response = api.post(base + '/next-question', json={'revision': first['revision']})
    assert response.status_code == 409
    assert [p['task'] for p in trace.payloads].count('followup_plan') == 1


def test_no_new_grounded_condition_returns_no_new_question(tmp_path):
    raw = {'candidates': [], 'missing_information': [], 'evidence_question': '',
           'why': '같은 조건을 이미 비교했고 새로운 구체적인 조건이 없습니다.'}
    api, _, base, _ = selected(tmp_path, RecommendationTrace([raw]))
    result = recommend(api, base)
    assert result['status'] == 'no_new_question' and not result['question']


def test_review_rejects_actual_performance_question_that_personas_cannot_answer(tmp_path):
    actual = 'SOUL의 타깃 추천이 실제로 정확한지 검증 결과를 알려주세요.'
    api, _, base, _ = selected(tmp_path, RecommendationTrace([plan(actual)], [review(answerable=False)]))
    result = recommend(api, base)
    assert result['status'] != 'discussion' and result['question'] != actual


def test_old_thread_citation_cannot_justify_current_thread_recommendation(tmp_path):
    api, _, base, original = selected(tmp_path, RecommendationTrace([plan(source='u1')], [review()]))
    new_revision(api, original, '리포트 검토 책임을 어떻게 인계하나요?', issue='검토 책임의 인계')
    result = recommend(api, base)
    assert result['status'] != 'discussion'


def test_superseded_public_view_is_not_resurrected_as_unresolved_condition(tmp_path):
    api, _, base, original = selected(tmp_path, RecommendationTrace([plan(source='u2')], [review()]))
    original.transcript.append(Utterance(id='u4', persona_id='p2', phase='group', round='Founder Follow-up',
        question=QUESTION, thread_id='th1', content='앞선 팀 수정 조건을 철회합니다. 현재 카드에서 더 추론할 근거가 없습니다.',
        reason='이전 조건을 유지할 근거 없음', dialogue_act='close'))
    original.threads[-1].utterance_ids.append('u4')
    api.app.state.store.put(original)
    result = recommend(api, base)
    assert result['status'] != 'discussion' and 'u2' not in result['source_utterance_ids']


def test_generated_numbers_are_not_reused_as_empirical_question_premises(tmp_path):
    numeric = '추천 정확도가 95%인 상황에서 검토 과정은 어떻게 달라지나요?'
    api, trace, base, original = selected(tmp_path, RecommendationTrace([plan(numeric)], [review()]))
    original.transcript[2].content += ' 실제 자료 없는 생성된 예시: 추천 정확도 95%.'
    api.app.state.store.put(original)
    result = recommend(api, base)
    assert result['status'] != 'discussion' and result['question'] != numeric
    assert all(p['task'] != 'followup_review' for p in trace.payloads)


def test_incomplete_semantic_review_cannot_approve_question(tmp_path):
    api, _, base, _ = selected(tmp_path, RecommendationTrace([plan()], [{'reviews': []}]))
    assert recommend(api, base)['status'] != 'discussion'


def test_persisted_offer_is_returned_after_server_restart_without_regeneration(tmp_path):
    api, _, base, _ = selected(tmp_path, RecommendationTrace([plan()], [review()]))
    first = recommend(api, base)
    restarted_trace = RecommendationTrace()
    restarted_api = TestClient(create_app(api.app.state.store.path, restarted_trace))
    assert recommend(restarted_api, base) == first
    assert not restarted_trace.payloads


def test_qwen_http_grammar_only_allows_visible_public_references_and_review_indices():
    import httpx
    from backend.schemas import FollowupPlan, FollowupReview
    bodies = []
    outputs = [plan(), review()]

    def handler(request):
        if request.url.path in ('/props', '/apply-template'):
            return httpx.Response(404)
        if request.url.path == '/tokenize':
            return httpx.Response(200, json={'tokens': [1] * 100})
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(outputs.pop(0), ensure_ascii=False)}}]})

    llm = LLMClient('qwen', transport=httpx.MockTransport(handler))
    llm.call('followup_plan', {'latest_public': [{'id': 'u2', 'persona_id': 'p2', 'content': '공개 조건'}],
        'earlier_public_excerpts': [{'id': 'u1', 'content': '이전 공개 조건'}]}, FollowupPlan)
    llm.call('followup_review', {'candidates': [{'index': 0, **plan()['candidates'][0]}]}, FollowupReview)
    planner_schema = bodies[0]['response_format']['json_schema']['schema']
    assert planner_schema['$defs']['FollowupCandidate']['properties']['source_utterance_ids']['items']['enum'] == ['u2']
    reviewer_schema = bodies[1]['response_format']['json_schema']['schema']
    assert reviewer_schema['$defs']['FollowupJudgment']['properties']['index']['enum'] == [0]


@pytest.mark.parametrize('condition', ['no_personas', 'unfinished_thread'])
def test_recommendation_requires_selected_personas_and_completed_exchange(tmp_path, condition):
    api, trace, base, original = selected(tmp_path)
    if condition == 'no_personas':
        original.cards = []
        original.status = 'CREATED'
    else:
        original.threads[-1].status = 'active'
        original.dialogue_runtime['followup']['done'] = False
    api.app.state.store.put(original)
    response = api.post(base + '/next-question', json={})
    assert response.status_code == 409
    assert not trace.payloads


def test_model_failure_keeps_conversation_and_allows_explicit_retry(tmp_path):
    trace = RecommendationTrace([plan()], [review()])
    api, _, base, original = selected(tmp_path, trace)
    trace.fail_once = True
    failed = api.post(base + '/next-question', json={})
    assert failed.status_code == 502
    partial = api.app.state.store.get(original.id)
    assert partial.transcript == original.transcript and partial.cards == original.cards
    assert recommend(api, base)['status'] == 'discussion'
