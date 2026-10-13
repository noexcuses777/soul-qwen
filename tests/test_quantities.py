"""Synthetic in-memory provenance checks; no server, model or database."""
import copy
import pytest
from backend.quantities import quantity_texts, unsupported_quantities
from backend.context import PersonaAgent, ContextManager, fingerprint
from backend.schemas import (
    Core, Identity, PersonaCard, IdeaBrief, IdeaInput, Session, Utterance,
    Report, Insight, SECTIONS, ConversationThread, Evidence, EvidenceLevel,
)
from backend.services import guard_report_quantities, generate_report
from backend.adaptive import AdaptiveConversation
from backend.orchestrator import TurnController


@pytest.mark.parametrize('text',[
    '월 2회라면 검토하겠습니다.', '가격은 19,900원입니다.', '20분이면 충분합니다.',
    '7일 안에 완료해야 합니다.', '성공률이 80%라면 가능합니다.', '월2회가 기준입니다.',
    '월 2~3회는 필요합니다.', '비용은 $20입니다.', '변화가 -10%입니다.',
])
def test_absent_unit_quantities_are_rejected(text):
    assert unsupported_quantities(text,['빈도와 예산은 UNKNOWN'])


@pytest.mark.parametrize('source,response',[
    ('월 1만원 구독', '월 10,000원이라면 비교하겠습니다.'),
    ('월 2회라고 가정하면?', '월2회라면 준비 부담을 비교해야 합니다.'),
    ('20분을 쓸 수 있나요?', '20 분이라는 사용자 가정에서 판단하겠습니다.'),
    ('지표 80%', '80퍼센트라는 제공 지표를 확인해야 합니다.'),
    ('가격은 USD 20이 아니라 20달러', '20 USD를 가정했습니다.'),
])
def test_supplied_prices_and_human_assumptions_are_allowed(source,response):
    assert unsupported_quantities(response,[source]) == []


def test_period_and_range_are_not_invented_from_a_bare_number():
    assert unsupported_quantities('월 2회', ['주 2회'])
    assert unsupported_quantities('2~3회',['3회'])
    assert unsupported_quantities('월 10만원',['월 1만원'])


def test_ids_versions_urls_and_id_fields_are_not_quantity_anchors():
    text='p1:r2, source_12, Qwen3.5-4B, Q4_K_M, https://example.org/?price=2회'
    assert unsupported_quantities(text,[]) == []
    allowed=quantity_texts({'id':'2회','source_id':'80%','evidence_ids':['100원'],
        'session_state':{'reason':'7일'},'actual':'빈도 미확인'})
    assert allowed == ['빈도 미확인']
    assert unsupported_quantities('2회와 80%와 100원과 7일',allowed)


def card(pid='p1',budget='UNKNOWN'):
    result=PersonaCard(id=pid,immutable_core=Core(identity_context=Identity(segment='합성 인터뷰 준비 담당자')))
    result.immutable_core.decision_model.budget_constraint=budget
    return result


class Answers:
    """Serve controlled answers while exercising the actual repair/guard code."""
    mode='qwen'
    def __init__(self,*answers): self.answers=answers; self.calls=[]
    def call(self,task,payload,schema,**kwargs):
        self.calls.append(copy.deepcopy(payload))
        return schema.model_validate(copy.deepcopy(self.answers[min(len(self.calls)-1,len(self.answers)-1)]))


def brief(revenue='UNKNOWN'):
    return IdeaBrief(one_line='합성 고객 인터뷰 준비 도구',business_category='IT',revenue_model=revenue)


def respond(agent, idea=None, question='도입 조건을 비교해 주세요.', parent=None):
    return agent.answer(idea or brief(),'group','Founder Follow-up',
        '동료가 월 2회라고 말했습니다.' if parent else question,
        interaction=True,participants=['p1','p2'],dialogue_goal=question,
        conversation_step='cross_response' if parent else 'contribution',required_parent=parent)


def test_numeric_repair_happens_once_and_preserves_the_original_candidate():
    original='가설로는 월 2회라면 도입을 검토할 수 있습니다.'
    llm=Answers({'content':original,'reason':'빈도를 기준으로 판단'},
        {'content':'가설로는 실제 빈도와 준비 부담을 확인해야 판단할 수 있습니다.','reason':'빈도 미확인'})
    agent=PersonaAgent(card(),llm); original_core=fingerprint(agent.card)
    answer=respond(agent)
    assert len(llm.calls)==2 and llm.calls[1]['correction_request']['issue']=='unsupported_quantity'
    assert answer.generated_content==original
    assert answer.quality_flags==['unsupported_quantity_repaired']
    assert '2회' not in answer.content and fingerprint(agent.card)==original_core


def test_invalid_numeric_memory_is_omitted_from_prompt_and_repair_but_retained_for_audit():
    original='월 3회라는 조건이면 비교하겠습니다.'
    llm=Answers({'content':original,'reason':'새 임계값'},
        {'content':'월2회라는 질문의 가정에서 실제 준비 부담을 확인해야 합니다.','reason':'사용자 가정'})
    agent=PersonaAgent(card(budget='20분의 준비 노력'),llm)
    question='월 2회라고 가정하면 어떤가요?'
    agent.context.add({'id':'old-invalid','persona_id':'p1','phase':'group','question':'이전 질문','content':'80%라는 생성 가설'})
    agent.context.add({'id':'old-valid','persona_id':'p1','phase':'group','question':'이전 질문','content':'월 10,000원에 20분이라는 제공 조건'})
    agent.context.add({'id':'current-invalid','persona_id':'p1','phase':'group','question':question,'content':'월 3회라는 생성 가설'})
    parent={'id':'peer','persona_id':'p2','phase':'group','content':'동료가 말한 80% 조건'}
    saved=copy.deepcopy(agent.context.recent); immutable=fingerprint(agent.card)
    answer=respond(agent,brief('월 1만원'),question,parent)
    own=llm.calls[0]['own']
    assert own['recent']==[] and own['omitted_invalid_numeric_history'] is True
    assert [v['id'] for v in own['prior_view_excerpts']]==['old-valid']
    assert '20분' in own['prior_view_excerpts'][0]['content']
    assert llm.calls[0]['required_parent']==parent and llm.calls[1]['required_parent']==parent
    assert llm.calls[1]['correction_request']['candidate']=='Unanchored numerical candidate withheld; regenerate from own card and human root question'
    assert original not in str(llm.calls[1])
    assert answer.generated_content==original and answer.quality_flags==['unsupported_quantity_repaired']
    assert agent.context.recent==saved and fingerprint(agent.card)==immutable


def test_permitted_numeric_memory_and_non_numeric_repair_candidate_remain_visible():
    original='구매하겠습니다.'
    llm=Answers({'content':original,'reason':'구매 확정'},
        {'content':'월 1만원에 20분의 준비 부담이라면 실제 도입 조건을 비교해야 합니다.','reason':'제공 조건'})
    agent=PersonaAgent(card(budget='20분의 준비 노력'),llm)
    agent.context.add({'id':'old-valid','persona_id':'p1','phase':'group','content':'월 10,000원에 20분이라는 제공 조건'})
    answer=respond(agent,brief('월 1만원'))
    assert len(llm.calls)==2 and llm.calls[1]['correction_request']['candidate']==original
    assert 'omitted_invalid_numeric_history' not in llm.calls[0]['own']
    assert llm.calls[0]['own']['prior_view_excerpts'][0]['id']=='old-valid'
    assert answer.generated_content==original and 'purchase_overclaim_repaired' in answer.quality_flags


def test_failed_repair_withholds_the_threshold_even_when_peer_and_own_memory_repeat_it():
    original='가설로는 월 2회라면 충분합니다.'
    llm=Answers({'content':original,'reason':'월 2회 기준','followup_question':'월 2회면 충분할까요?',
                 'followup_kind':'peer_condition','addressed_to':'p2'})
    agent=PersonaAgent(card(),llm)
    agent.context.add({'id':'old','persona_id':'p1','phase':'group','content':original})
    parent={'id':'peer','persona_id':'p2','phase':'group','content':original}
    before=copy.deepcopy(agent.context.recent)
    answer=respond(agent,parent=parent)
    assert len(llm.calls)==2 and answer.generated_content==original
    assert 'unsupported_quantity_withheld' in answer.quality_flags
    assert '2회' not in answer.content+answer.reason+' '.join(answer.unresolved_issues)
    assert answer.followup_question=='' and answer.addressed_to is None and answer.stance=='conditional'
    assert agent.context.recent==before


def test_quantities_in_reason_or_followup_are_also_held():
    llm=Answers({'content':'조건을 확인해야 합니다.','reason':'소요 시간은 30분입니다.',
                 'followup_question':'5일 안에 쓸 수 있나요?','followup_kind':'real_world_check'})
    answer=respond(PersonaAgent(card(),llm))
    assert len(llm.calls)==2 and 'unsupported_quantity_withheld' in answer.quality_flags
    assert '30분' not in answer.reason and not answer.followup_question


def test_numeric_basis_uses_own_card_founder_price_and_current_human_question():
    llm=Answers({'content':'월 10,000원에 20분의 준비 노력이라면 비교하겠습니다.','reason':'주어진 조건'})
    answer=respond(PersonaAgent(card(budget='20분의 준비 노력'),llm),
                   idea=brief('월 1만원'),question='제공 가격을 어떻게 볼까요?')
    assert len(llm.calls)==1 and not answer.quality_flags
    llm=Answers({'content':'월2회라는 질문의 가정에서 효과를 비교해야 합니다.','reason':'사용자 가정'})
    answer=respond(PersonaAgent(card(),llm),question='월 2회라고 가정하면 어떤가요?')
    assert len(llm.calls)==1 and not answer.quality_flags


def test_noninteractive_private_answer_uses_the_same_numeric_guard_and_schema():
    llm=Answers({'content':'월 3회는 필요합니다.'})
    answer=PersonaAgent(card(),llm).answer(brief(),'pre','Private Pre','최초 의견은?')
    assert len(llm.calls)==2 and 'unsupported_quantity_withheld' in answer.quality_flags
    assert answer.generated_content=='월 3회는 필요합니다.'


def report_fixture():
    turn=Utterance(id='u1',persona_id='p1',phase='group',round='Founder Follow-up',
        question='빈도를 어떻게 볼까요?',content='월 2회라는 생성 가설',reason='월 2회 판단 기준',thread_id='th1')
    report=Report(sections={name:[Insight(text='합성 인사이트',utterance_ids=['u1'])] for name in SECTIONS})
    report.sections['Real Interview Next Steps'][0].text='월 2회 인터뷰를 한다면 비용은 어떤가요?'
    return Session(id='numeric-fixture',input=IdeaInput(q1='합성 준비 도구',q5='IT'),brief=brief(),
        targets=[],cards=[card()],transcript=[turn],report=report,report_revision=1,mode='mock',
        threads=[ConversationThread(id='th1',question='빈도를 어떻게 볼까요?',utterance_ids=['u1'])])


def test_ai_citations_cannot_ground_numeric_real_customer_questions_and_raw_audit_is_preserved():
    session=report_fixture(); report=session.report.model_copy(deep=True)
    original=report.sections['Real Interview Next Steps'][0].model_dump(mode='json')
    before=session.model_dump(mode='json')['transcript']
    result=guard_report_quantities(session,report,revision=1)
    assert result.sections['Real Interview Next Steps']==[]
    row=result.sections['Unknown/Unsupported'][-1]
    assert '월 2회' in row.text and row.confidence=='low'
    assert session.dialogue_runtime['report_claim_audits'][-1]['original_claim']==original
    assert '질문을 다시 구성' in result.notice
    assert session.model_dump(mode='json')['transcript']==before
    # A second projection does not duplicate the classification or its notice.
    notice=result.notice; count=len(session.dialogue_runtime['report_claim_audits'])
    guard_report_quantities(session,result,revision=1)
    assert result.notice==notice and len(session.dialogue_runtime['report_claim_audits'])==count


def test_report_questions_can_use_founder_prices_human_assumptions_and_cited_evidence():
    session=report_fixture()
    session.brief.revenue_model='월 1만원'
    session.threads[0].question='월 2회라면 어떻게 판단할까요?'
    row=session.report.sections['Real Interview Next Steps'][0]
    row.text='월 10,000원에 월2회로 가정한 조건을 확인할까요?'
    assert guard_report_quantities(session,session.report,1).sections['Real Interview Next Steps']
    session.input.evidence=[Evidence(source_id='real-source',text='소요 시간은 30분',level=EvidenceLevel.L3)]
    row.text='원자료의 30분 조건이 맞나요?'; row.evidence_ids=['real-source']
    assert guard_report_quantities(session,session.report,1).sections['Real Interview Next Steps']


def test_projected_legacy_report_guard_does_not_rewrite_saved_source_or_use_future_questions():
    session=report_fixture(); source=copy.deepcopy(session.model_dump(mode='json'))
    session.threads.append(ConversationThread(id='th2',question='월 2회라면?',utterance_ids=['future']))
    detached=session.model_copy(deep=True)
    result=guard_report_quantities(detached,detached.report,revision=1)
    assert not result.sections['Real Interview Next Steps']
    assert session.report.sections['Real Interview Next Steps'][0].text==source['report']['sections']['Real Interview Next Steps'][0]['text']
    assert not session.dialogue_runtime


def test_new_report_generation_applies_numeric_guard_without_an_extra_model_call():
    session=report_fixture()
    class ReportOnly:
        calls=0
        def call(self,*args,**kwargs): self.calls+=1; return session.report.model_copy(deep=True)
    llm=ReportOnly()
    report=generate_report(session,llm)
    assert llm.calls==1 and not report.sections['Real Interview Next Steps']


def post_session():
    session=report_fixture()
    session.cards.append(card('p2'))
    session.threads[0].question='월 2회라고 가정하면 어떻게 판단할까요?'
    session.dialogue_runtime['followup']={'thread_id':'th1','done':True}
    session.transcript.append(Utterance(id='peer',persona_id='p2',phase='group',round='Founder Follow-up',
        question='동료 조건',content='80%라는 동료의 생성 가설',thread_id='th1'))
    session.threads[0].utterance_ids.append('peer')
    return session


def test_private_post_receives_only_the_snapshot_human_question_as_numeric_basis():
    session=post_session()
    llm=Answers({'content':'월2회라는 사용자 가정에서 실제 준비 부담을 확인하겠습니다.','reason':'사용자 가정'})
    dialogue=AdaptiveConversation(llm,TurnController()); dialogue.restore(session)
    before=[fingerprint(c) for c in session.cards]
    result=dialogue.speak('p1','post','Private Post','마지막 독립 의견',lambda s:None,snapshot_revision=2)
    assert llm.calls[0]['human_question']==session.threads[0].question
    assert any('80%' in t['content'] for t in llm.calls[0]['group']['recent'])
    assert len(llm.calls)==1 and not result.quality_flags
    assert [fingerprint(c) for c in session.cards]==before


def test_private_post_does_not_promote_peer_numeric_claims_to_user_evidence():
    session=post_session()
    original='월 2회에서 80%라면 검토할 수 있습니다.'
    llm=Answers({'content':original,'reason':'동료 가설을 따름'})
    dialogue=AdaptiveConversation(llm,TurnController()); dialogue.restore(session)
    result=dialogue.speak('p1','post','Private Post','마지막 독립 의견',lambda s:None,snapshot_revision=2)
    assert len(llm.calls)==2 and 'unsupported_quantity_withheld' in result.quality_flags
    assert result.generated_content==original and '80%' not in result.content
    assert llm.calls[-1]['human_question']==session.threads[0].question


@pytest.mark.parametrize('future',[False,True])
def test_private_post_without_a_visible_human_thread_keeps_question_none(future):
    session=post_session()
    if future:
        session.threads[0].utterance_ids.append('after-snapshot')
    else:
        session.threads=[]
    llm=Answers({'content':'실제 빈도를 확인해야 판단할 수 있습니다.'})
    dialogue=AdaptiveConversation(llm,TurnController()); dialogue.restore(session)
    dialogue.speak('p1','post','Private Post','마지막 독립 의견',lambda s:None,snapshot_revision=2)
    assert llm.calls[0]['human_question'] is None
