import json
from pathlib import Path
import pytest
from backend.schemas import *
from backend.llm import LLMClient
from backend.services import *
from backend.context import ContextManager,PersonaAgent,fingerprint
from backend.orchestrator import Orchestrator,TurnController

@pytest.fixture
def setup():
    i=IdeaInput(q1='면접 질문 준비 도구',q5='IT'); llm=LLMClient('mock'); b=parse_idea(i); ts=generate_targets(b,[],llm); cards=[]
    for n,t in enumerate(ts[:3]): cards.append(build_card(t,cards,[],llm,f'p{n+1}')[0])
    return i,llm,b,ts,cards

def test_unknown_preservation():
    b=parse_idea(IdeaInput(q1='idea',q5='IT'))
    assert b.pricing==b.expected_user==b.problem=='UNKNOWN'
    assert b.current_alternatives==[]
    with pytest.raises(ValueError): IdeaInput(q1='idea',q5='missing')
    with pytest.raises(ValueError): Selection(target_ids=['a']*2)
    with pytest.raises(ValueError): Selection(target_ids=['a','b','c','d'])

def test_legacy_idea_without_description_keeps_problem_wording():
    b=parse_idea(IdeaInput(q1='idea',q3_1='차별점과 해결 문제',q3_2='구독',q4_1='학교 PoC',q5='IT'))
    assert b.problem==b.solution==b.value_proposition=='차별점과 해결 문제'
    assert b.revenue_model=='구독'
    assert b.realization==b.go_to_market=='학교 PoC'

def test_frontend_idea_fields_keep_description_problem_and_customer_type_separate():
    i=IdeaInput(q1='예약 서비스',q3='동네 서점 재고 예약',q3_1='전화 확인이 번거롭다',
                customer_type='개인 고객에게 팝니다',founder_strength='서점 운영 경험',q5='유통/물류')
    b=parse_idea(i)
    assert b.solution=='동네 서점 재고 예약'
    assert b.problem=='전화 확인이 번거롭다'
    assert b.customer_type=='개인 고객에게 팝니다'
    assert b.founder_strength=='서점 운영 경험'
    assert b.expected_user=='UNKNOWN'
    assert parse_idea(IdeaInput(q1='예약 서비스',q5='IT')).customer_type=='UNKNOWN'

def test_target_contrast(setup):
    _,_,_,ts,_=setup
    assert len({contrast_signature(t) for t in ts})==len(ts)
    assert all(t.confidence=='low' and t.evidence_level==0 for t in ts)

def test_relevance_contrast_rank():
    a=Target(segment_name='one',why_relevant='test',problem_exposure='daily repetitive manual task',buying_role='user',relevance=.95)
    b=Target(segment_name='two',why_relevant='test',problem_exposure='daily repetitive manual work',buying_role='user',relevance=.9)
    c=Target(segment_name='three',why_relevant='test',problem_exposure='institution procurement approval',buying_role='buyer',relevance=.85)
    ranked=rank_contrasting([a,b,c]);assert ranked[0]==a and ranked[1]==c

def test_validator_and_repair(setup):
    _,llm,_,ts,cards=setup
    bad=cards[0].model_copy(deep=True); bad.immutable_core.identity_context.age='24'
    result=validate_card(bad,ts[0],[],[],llm)
    assert not result.valid and any('age' in i.detail for i in result.issues)
    assert not validate_card(cards[0],ts[0],[cards[0]],[],llm).valid
    source=Evidence(source_id='real1',text='나이: 24',level=3)
    bad.immutable_core.evidence_anchors.append(Anchor(source_id='real1',field='identity_context.age',quote='나이: 24',level=3))
    assert validate_card(bad,ts[0],[],[source],llm).valid
    bad.immutable_core.evidence_anchors[0].quote='나이: 25'
    assert not validate_card(bad,ts[0],[],[source],llm).valid
    class Reject(LLMClient):
        def call(self,task,payload,schema,**kwargs):
            if task=='validate': return ValidationResult(issues=[ValidationIssue(kind='stereotype',detail='test')])
            return super().call(task,payload,schema,**kwargs)
    with pytest.raises(ValueError,match='3 builds'): build_card(ts[0],[],[],Reject('mock'),'p1')

def test_grounding_gate_keeps_target_and_removes_unanchored_detail(setup):
    _,_,_,targets,cards=setup
    card=cards[0].model_copy(deep=True)
    card.immutable_core.problem_context.problem_severity='매우 심각함'
    card.immutable_core.decision_model.adoption_barrier='비용'
    card.immutable_core.goals_motivations.desired_outcome='매출 증가'
    card.immutable_core.identity_context.use_context='임의 상황'
    normalized=normalize_card(card,targets[0],[])
    assert normalized.immutable_core.problem_context.problem_severity==UNKNOWN
    assert normalized.immutable_core.decision_model.adoption_barrier==UNKNOWN
    assert normalized.immutable_core.goals_motivations.desired_outcome==UNKNOWN
    assert normalized.immutable_core.identity_context.use_context==targets[0].problem_exposure

def test_subjective_llm_audit_is_advisory_after_hard_gate(setup):
    _,_,_,targets,cards=setup
    class AuditNoise(LLMClient):
        def call(self,task,payload,schema,**kwargs):
            if task=='validate':
                return ValidationResult(issues=[ValidationIssue(kind='unknown_handling',detail='too sparse')])
            return super().call(task,payload,schema,**kwargs)
    result=validate_card(cards[0],targets[0],[],[],AuditNoise('mock'))
    assert result.valid and result.advisory[0].kind=='unknown_handling'

def test_private_context_isolation(setup):
    _,llm,b,_,cards=setup
    a=PersonaAgent(cards[0],llm); c=PersonaAgent(cards[1],llm)
    a.context.add({'id':'private-secret','persona_id':'p1','phase':'pre','content':'private secret'})
    assert 'private secret' not in json.dumps(c.context.view())
    a.state.reasons.append('private reason')
    assert not c.state.reasons
    assert fingerprint(a.card)==fingerprint(cards[0])
    # Runtime fingerprint catches nested core edits, which Pydantic's shallow frozen cannot prevent.
    a.card.immutable_core.identity_context.age='99'
    with pytest.raises(ValueError,match='immutable'): a.answer(b,'pre','pre','question')

def test_invalid_private_reply_reference_is_discarded(setup):
    _,_,brief,_,cards=setup
    class InvalidReply(LLMClient):
        def call(self,task,payload,schema,**kwargs):
            if task=='agent': return AgentAnswer(content='독립 응답',reply_to='UNKNOWN')
            return super().call(task,payload,schema,**kwargs)
    answer=PersonaAgent(cards[0],InvalidReply('mock')).answer(brief,'pre','Private Pre','question')
    assert answer.reply_to is None

def test_actual_prompt_visibility(setup):
    i,_,b,ts,cards=setup
    class Trace(LLMClient):
        def __init__(self):super().__init__('mock');self.payloads=[]
        def call(self,task,payload,schema,**kw):
            if task=='agent': self.payloads.append(payload)
            return super().call(task,payload,schema,**kw)
    llm=Trace();s=Session(id='trace',input=i,brief=b,targets=ts,cards=cards,mode='mock');Orchestrator(llm).run(s)
    for payload in llm.payloads:
        own=payload['card']['id']
        assert len(payload['own']['recent'])<=4 and len(payload['group']['recent'])<=6
        assert all(t['persona_id']==own for t in payload['own']['recent'])
        assert all(t['phase']=='group' for t in payload['group']['recent'])
        if payload['phase']=='pre':assert not payload['group']['recent']
        assert ' pre]' not in payload['group']['older_summary'] and ' post]' not in payload['group']['older_summary']

def test_summary_buffer():
    c=ContextManager(recent=8,summary_chars=1600)
    for n in range(100): c.add({'id':str(n),'persona_id':'p1','phase':'group','content':'hello'*100})
    assert len(c.recent)==8 and len(c.summary)<=1600 and 'p1 group' in c.summary

@pytest.mark.parametrize('n,total,group',[(1,14,12),(2,16,12),(3,24,18)])
def test_group_flow(setup,n,total,group):
    i,llm,b,ts,cards=setup
    s=Session(id='s',input=i,brief=b,targets=ts,cards=cards[:n],mode='mock'); before=[fingerprint(c) for c in s.cards]
    Orchestrator(llm).run(s)
    assert s.status=='COMPLETE' and len(s.transcript)==total
    assert len([t for t in s.transcript if t.phase=='group'])==group
    assert s.state_history==['CREATED','PRE','GROUP','POST','REPORT','COMPLETE']
    assert set(s.report.sections)==set(SECTIONS) and [fingerprint(c) for c in s.cards]==before
    assert all(t.reply_to is None for t in s.transcript if t.phase=='pre')
    assert set(s.states)=={c.id for c in s.cards}

def test_controller_mentions(setup):
    _,llm,_,_,cards=setup; agents={c.id:PersonaAgent(c,llm) for c in cards}; public=ContextManager()
    public.add({'id':'g','persona_id':'p1','phase':'group','content':'p3 의견을 듣고 싶어요'})
    assert TurnController().select(list(agents),agents,'question',public,4,{})=='p3'

def test_unknown_source_no_promotion(setup):
    _,llm,b,_,_=setup
    class Invent(LLMClient):
        def call(self,task,payload,schema,**kw):
            data=super().call(task,payload,schema,**kw)
            data.targets[0].evidence_ids=['fake']; return data
    with pytest.raises(ValueError,match='invented evidence'): generate_targets(b,[],Invent('mock'))
