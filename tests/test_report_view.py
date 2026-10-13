"""Report projection tests verify provenance and scope, not market validity."""
import copy
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient
from backend.report_view import report_view
from backend.schemas import (
    Session, IdeaInput, IdeaBrief, PersonaCard, Core, Identity, Presentation,
    Utterance, Report, Insight, SECTIONS, ConversationThread, QuestionSuggestion,
    Evidence, EvidenceLevel,
)


def fixture():
    cards = [PersonaCard(id=f'p{n}', immutable_core=Core(identity_context=Identity(
        segment=f'이용자 유형 {n}')), presentation=Presentation(display_name=f'참여자{n}'))
        for n in (1, 2, 3)]
    turns = [
        Utterance(id='pre1', persona_id='p1', phase='pre', round='Private Pre',
                  question='첫 생각', content='독립적인 최초 의견'),
        Utterance(id='u1', persona_id='p1', phase='group', round='Founder Follow-up',
                  question='도입 조건은?', content='먼저 도입을 검토할 수 있습니다.',
                  stance='positive', reason='현재 조건과 맞음', thread_id='th1'),
        Utterance(id='u2', persona_id='p2', phase='group', round='Founder Follow-up',
                  question='도입 조건은?', content='예산은 확인하지 못했습니다.',
                  stance='unknown', reason='정보 부족', thread_id='th1',
                  unresolved_issues=['예산 미확인'], followup_question='실제 예산 범위는?',
                  followup_kind='real_world_check'),
        Utterance(id='u3', persona_id='p1', phase='group', round='Founder Follow-up',
                  question='동료 의견을 비교하세요.', content='검증 비용이 크다면 조건부로 바꾸겠습니다.',
                  stance='conditional', reason='검증 비용 조건이 추가되어 판단을 바꿈',
                  thread_id='th1', reply_to='u2'),
        Utterance(id='u4', persona_id='p3', phase='group', round='Founder Follow-up',
                  question='다른 질문', content='제 조건에서는 반대입니다.',
                  stance='negative', reason='전환 부담', thread_id='th2'),
        Utterance(id='post1', persona_id='p1', phase='post', round='Private Post',
                  question='최종 의견', content='조건은 실제 인터뷰로 확인해야 합니다.',
                  snapshot_revision=4),
    ]
    rows = {name: [Insight(text=name+'의 원래 가설', utterance_ids=['u1'])]
            for name in SECTIONS}
    return Session(id='report-fixture', input=IdeaInput(q1='검증 도구', q5='IT'),
                   brief=IdeaBrief(one_line='검증 도구', business_category='IT'),
                   targets=[], cards=cards, transcript=turns,
                   report=Report(sections=rows), report_revision=4,
                   report_generated_at='2026-10-05T00:00:00+00:00', mode='mock',
                   threads=[ConversationThread(id='th1', question='도입 조건은?',
                                               utterance_ids=['u1','u2','u3']),
                            ConversationThread(id='th2', question='다른 질문', utterance_ids=['u4'])])


def test_report_view_preserves_original_insights_quotes_and_source_session():
    session = fixture()
    before = copy.deepcopy(session.model_dump(mode='json'))
    view = report_view(session)
    assert session.model_dump(mode='json') == before
    assert view['meta']['persona_count'] == 3
    assert view['meta']['question_count'] == 2
    assert view['meta']['public_turn_count'] == 4
    assert view['meta']['insight_count'] == len(view['new_insights']) == 2
    assert view['meta']['change_count'] == len(view['changes']) == 1
    assert view['meta']['unknown_count'] == len(view['unknowns']) == 2
    assert view['meta']['generated_at'] == session.report_generated_at
    assert set(view['sections']) == set(SECTIONS)
    assert view['topics'][0]['question'] == '도입 조건은?'
    p1 = view['topics'][0]['positions'][0]
    assert p1['utterance_id'] == 'u3' and p1['content'] == session.transcript[3].content
    assert view['sections']['Problem Signal'][0]['text'] == session.report.sections['Problem Signal'][0].text
    assert {source['id'] for source in view['sources']} == {turn.id for turn in session.transcript}


def test_stale_report_does_not_absorb_new_topics_posts_or_suggestions():
    session = fixture()
    session.report_stale = True
    session.transcript += [
        Utterance(id='u5', persona_id='p1', phase='group', round='Founder Follow-up',
                  question='리포트 이후 새 질문', content='새 질문에 대한 의견',
                  stance='negative', reason='다른 조건', thread_id='th3'),
        Utterance(id='post2', persona_id='p1', phase='post', round='Private Post',
                  question='새 최종 의견', content='새 사후 의견', snapshot_revision=5),
    ]
    session.threads.append(ConversationThread(id='th3', question='리포트 이후 새 질문', utterance_ids=['u5']))
    session.suggestions = [QuestionSuggestion(question='새 질문에서 만든 추천', why='새 조건', topic='Failure Condition')]
    view = report_view(session)
    assert view['meta']['stale'] and view['meta']['revision'] == 4
    assert view['meta']['question_count'] == 2 and view['meta']['public_turn_count'] == 4
    assert 'u5' not in {source['id'] for source in view['sources']}
    assert 'post2' not in {source['id'] for source in view['sources']}
    assert not any(row['kind']=='suggestion' for row in view['followups'])
    assert view['meta']['generated_at'] == '2026-10-05T00:00:00+00:00'


def test_changes_require_same_topic_known_stances_and_a_reason():
    session = fixture()
    session.transcript += [
        Utterance(id='u5', persona_id='p1', phase='group', round='Founder Follow-up',
                  question='다른 질문', content='다른 질문에는 반대입니다.',
                  stance='negative', reason='다른 조건', thread_id='th2'),
        Utterance(id='u6', persona_id='p2', phase='group', round='Founder Follow-up',
                  question='도입 조건은?', content='조건이 확인되면 고려합니다.',
                  stance='conditional', reason='추가 조건', thread_id='th1'),
        Utterance(id='u7', persona_id='p1', phase='group', round='Founder Follow-up',
                  question='도입 조건은?', content='반대합니다.',
                  stance='negative', reason='UNKNOWN', thread_id='th1'),
    ]
    session.report_revision = 7
    changes = report_view(session)['changes']
    assert len(changes) == 1 and changes[0]['utterance_ids'] == ['u1','u3']
    assert changes[0]['before']['stance']=='positive' and changes[0]['after']['stance']=='conditional'


def test_guarded_corrections_are_not_reported_as_opinion_changes():
    session = fixture()
    session.transcript[3].quality_flags = ['persona_identity_mismatch_withheld']
    assert report_view(session)['changes'] == []


def test_invalid_or_future_insight_references_are_withheld():
    session = fixture()
    session.report.sections['Agreement'] = [Insight(text='근거 없는 전체 합의', utterance_ids=['future'])]
    session.report.sections['Disagreement'] = [Insight(text='없는 원자료', utterance_ids=['u1'], evidence_ids=['fake'])]
    view = report_view(session)
    assert not view['sections']['Agreement'] and not view['sections']['Disagreement']
    assert view['meta']['excluded_insight_count'] == 2
    assert all('근거 없는' not in row['text'] for row in view['conclusion'])


def test_old_universal_agreement_is_guarded_without_rewriting_history():
    session = fixture()
    row = session.report.sections['Agreement'][0]
    row.text = '모든 참여자가 도입에 동의했습니다.'
    row.confidence = 'high'
    before = session.model_dump(mode='json')
    view = report_view(session)
    displayed = view['sections']['Agreement'][0]
    assert '인용 근거가 부족' in displayed['text'] and displayed['confidence'] == 'low'
    assert session.model_dump(mode='json') == before


def test_unknowns_deduplicate_and_keep_each_exact_citation():
    session = fixture()
    session.transcript[3].unresolved_issues = ['예산 미확인']
    rows = report_view(session)['unknowns']
    row = next(row for row in rows if row['text']=='예산 미확인')
    assert row['utterance_ids'] == ['u2','u3']


def test_pending_thread_condition_does_not_acquire_fabricated_quote_ids():
    session = fixture()
    session.threads[0].remaining_issues = ['응답 한도로 남은 조건']
    row = next(row for row in report_view(session)['unknowns']
               if row['text']=='응답 한도로 남은 조건')
    assert row['utterance_ids'] == [] and row['evidence_ids'] == []


def test_followups_keep_real_world_checks_but_omit_answered_peer_requests():
    session = fixture()
    session.transcript[1].followup_question = '어떤 예산 조건인가요?'
    session.transcript[1].followup_kind = 'peer_condition'
    session.transcript[1].addressed_to = 'p2'
    session.transcript[2].reply_to = 'u1'
    view = report_view(session)
    assert [row['question'] for row in view['followups']] == ['실제 예산 범위는?']
    assert view['followups'][0]['utterance_ids'] == ['u2']


def test_legacy_records_have_no_invented_timestamp_or_later_topic_change():
    session = fixture()
    session.report_revision = None
    session.report_generated_at = None
    session.threads = []
    for turn in session.transcript:
        turn.thread_id = None
    view = report_view(session)
    assert view['meta']['generated_at'] is None and view['meta']['revision_inferred']
    assert view['meta']['question_count'] == 2


def test_empty_report_returns_409_and_unknown_session_404(tmp_path):
    api = TestClient(create_app(str(tmp_path/'view.db'), LLMClient('mock')))
    session = fixture()
    session.report = None
    api.app.state.store.put(session)
    assert api.get('/api/sessions/report-fixture/report-view').status_code == 409
    assert api.get('/api/sessions/missing/report-view').status_code == 404


def test_api_view_is_read_only_and_has_no_additional_llm_call(tmp_path):
    client = LLMClient('mock')
    api = TestClient(create_app(str(tmp_path/'view.db'), client))
    session = fixture()
    api.app.state.store.put(session)
    source = api.get('/api/sessions/report-fixture').json()
    first = api.get('/api/sessions/report-fixture/report-view')
    second = api.get('/api/sessions/report-fixture/report-view')
    assert first.status_code == 200 and first.json() == second.json()
    assert api.get('/api/sessions/report-fixture').json() == source
    assert client.records == []


def test_report_timestamp_persists_and_cached_finish_keeps_it(tmp_path):
    client = LLMClient('mock')
    api = TestClient(create_app(str(tmp_path/'stamp.db'), client))
    response = api.post('/api/sessions', json={'q1':'고객 인터뷰 준비 도구','q5':'IT'})
    base = '/api/sessions/'+response.json()['id']
    assert api.post(base+'/select',json={'target_ids':['t1']}).status_code == 200
    assert api.post(base+'/ask',json={'question':'어떤 조건에서 쓸까요?'}).status_code == 200
    completed = api.post(base+'/finish',json={}).json()
    timestamp = completed['report_generated_at']
    assert timestamp and timestamp.endswith('+00:00')
    calls = len(client.records)
    assert api.post(base+'/finish',json={}).json()['report_generated_at'] == timestamp
    assert len(client.records) == calls
    assert api.get(base+'/report-view').json()['meta']['generated_at'] == timestamp


def test_followup_buttons_exclude_statements_and_preserve_raw_turns():
    session = fixture()
    session.transcript[1].followup_question = '현재 대안이 더 합리적입니다.'
    session.transcript[1].followup_kind = 'real_world_check'
    session.transcript[3].followup_question = '서로의 전환 조건을 비교해 주세요.'
    session.transcript[3].followup_kind = 'peer_condition'
    original = copy.deepcopy(session.model_dump(mode='json'))
    questions = [row['question'] for row in report_view(session)['followups']]
    assert '현재 대안이 더 합리적입니다.' not in questions
    assert '실제 예산 범위는?' in questions
    assert '서로의 전환 조건을 비교해 주세요.' in questions
    assert session.model_dump(mode='json') == original


def test_legacy_numeric_interview_prompt_is_unconfirmed_without_rewriting_history():
    session = fixture()
    session.transcript[1].followup_question = '월 7회 사용하면 도움이 될까요?'
    session.transcript[1].followup_kind = 'real_world_check'
    session.report.sections['Real Interview Next Steps'] = [
        Insight(text='월 7회 쓰는지 확인했나요?', utterance_ids=['u1'])]
    original = copy.deepcopy(session.model_dump(mode='json'))
    view = report_view(session)
    assert not view['real_interview']
    assert not any('7회' in row['question'] for row in view['followups'])
    assert any('근거가 확인되지 않은 수치' in row['text'] for row in view['unknowns'])
    assert session.model_dump(mode='json') == original


def test_report_json_preserves_corrected_candidate_and_claim_audit():
    session = fixture()
    session.transcript[1].generated_content = '근거 없이 생성된 73%라는 원문'
    session.transcript[1].quality_flags = ['unsupported_quantity_withheld']
    claim = Insight(text='월 7회 사용하는지 물어보세요.', utterance_ids=['u1'])
    session.report.sections['Real Interview Next Steps'] = [claim]
    original = copy.deepcopy(session.model_dump(mode='json'))
    view = report_view(session)
    assert next(row for row in view['sources'] if row['id'] == 'u1')['generated_content'] == session.transcript[1].generated_content
    assert view['audits'][-1]['original_claim'] == claim.model_dump(mode='json')
    assert session.model_dump(mode='json') == original
