import json
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient,LLMError
from backend.context import fingerprint,PersonaAgent
from backend.schemas import AgentAnswer,TimelineEvent,Session,Utterance
from backend.services import rule_issues

def prepared(tmp_path,llm=None,n=3):
    llm=llm or LLMClient('mock'); api=TestClient(create_app(str(tmp_path/'guided.db'),llm))
    s=api.post('/api/sessions',json={'q1':'검증할 인터뷰 준비 도구','q5':'IT'}).json()
    s=api.post(f'/api/sessions/{s["id"]}/select',json={'target_ids':[f't{i+1}' for i in range(n)]}).json()
    assert s['status']=='SELECTED'
    return api,llm,s

@pytest.mark.parametrize('n',[1,2,3])
def test_guided_flow_user_controls_start_thread_and_finish(tmp_path,n):
    api,llm,s=prepared(tmp_path,n=n); base=f'/api/sessions/{s["id"]}'
    before=len(llm.records); s=api.post(base+'/suggestions',json={}).json()
    assert len(s['suggestions'])==6 and len(llm.records)==before+1
    api.post(base+'/suggestions',json={}); assert len(llm.records)==before+1
    s=api.post(base+'/start',json={'mode':'guided'}).json()
    assert s['status']=='WAITING' and len(s['transcript'])==n and s['report'] is None
    assert all(t['phase']=='pre' for t in s['transcript'])
    s=api.post(base+'/ask',json={'question':'어떤 조건이 중요할까요?','interaction':'interactive'}).json()
    assert s['status']=='WAITING' and s['report'] is None
    assert n<=len(s['threads'][0]['utterance_ids'])<=5*n
    assert {t['persona_id'] for t in s['transcript'] if t['phase']=='group'}=={f'p{i+1}' for i in range(n)}
    assert s['threads'][0]['status']=='returned_to_user'
    assert all(t['thread_id']=='th1' for t in s['transcript'] if t['phase']=='group')
    s=api.post(base+'/ask',json={'question':'전환 비용은 알려졌나요?','persona_id':'p1','interaction':'direct'}).json()
    assert len(s['threads'][1]['utterance_ids'])==1
    s=api.post(base+'/finish',json={}).json()
    assert s['status']=='COMPLETE' and len(s['report']['sections'])==8
    assert sum(t['phase']=='post' for t in s['transcript'])==n
    assert not any(t['round']=='Closing check' for t in s['transcript'])
    assert all(t['status']=='returned_to_user' for t in s['threads'])
    before=len(llm.records)
    assert api.post(base+'/finish',json={}).status_code==200
    assert len(llm.records)==before

def test_names_are_cosmetic_and_old_cards_migrate(tmp_path):
    api,_,s=prepared(tmp_path); base=f'/api/sessions/{s["id"]}'
    before=[fingerprint(c) for c in Session.model_validate(s).cards]
    assert [c['presentation']['display_name'] for c in s['cards']]==[s['target_display_names'][target_id] for target_id in s['selected_target_ids']]
    renamed=api.post(base+'/names/p1',json={'display_name':'한서윤'}).json()
    assert [fingerprint(c) for c in Session.model_validate(renamed).cards]==before
    assert api.post(base+'/names/p2',json={'display_name':'한서윤'}).status_code==422
    assert api.post(base+'/names/p2',json={'display_name':'\n'}).status_code==422
    for c in s['cards']: c.pop('presentation')
    api.app.state.store.put(Session.model_validate(s))
    assert api.get(base).json()['cards'][0]['presentation']['display_name']==s['target_display_names']['t1']

def test_reasoning_and_timeline_cannot_launder_unknown_facts(tmp_path):
    _,_,s=prepared(tmp_path); card=Session.model_validate(s).cards[0]
    assert card.immutable_core.reasoning_rules[0].kind=='hypothesis'
    card.immutable_core.reasoning_rules[0].basis_fields=['decision_model.budget_constraint']
    assert rule_issues(card.immutable_core,[])
    card.immutable_core.timeline.append(TimelineEvent(source_id='fake',event_quote='지난해 사용했다'))
    assert any('timeline' in x for x in rule_issues(card.immutable_core,[]))

def test_context_contains_active_thread_not_unrelated_recent_or_private(tmp_path):
    class Trace(LLMClient):
        def __init__(self): super().__init__('mock'); self.payloads=[]
        def call(self,task,payload,schema,**kw):
            if task in ('interact','chat'): self.payloads.append(payload)
            return super().call(task,payload,schema,**kw)
    trace=Trace(); api,_,s=prepared(tmp_path,trace); base=f'/api/sessions/{s["id"]}'
    api.post(base+'/start',json={})
    api.post(base+'/ask',json={'question':'첫 질문','interaction':'interactive'})
    trace.payloads=[]
    api.post(base+'/ask',json={'question':'둘째 질문','interaction':'interactive'})
    assert trace.payloads and not trace.payloads[0]['group']['recent']
    for p in trace.payloads:
        assert 'presentation' not in p['card']
        assert all(t['phase']=='group' for t in p['group']['recent'])
        assert all(t['persona_id']==p['card']['id'] for t in p['own']['recent'])
        assert not re_private(p['group'])

def re_private(value): return ' pre]' in json.dumps(value) or ' post]' in json.dumps(value)

def test_question_schema_has_unique_controller_owned_topics():
    from backend.schemas import QuestionPlan
    from backend.prompts import ROUNDS
    raw=QuestionPlan.model_json_schema()['properties']['suggestions']
    assert set(raw['required'])=={name for name,_ in ROUNDS} and raw['additionalProperties'] is False
    model=QuestionPlan.model_validate({'suggestions':{name:{'question':q,'why':'조건 확인'} for name,q in ROUNDS}})
    assert {s.topic for s in model.suggestions}==set(raw['required'])

def test_atomic_diagnostics_require_explicit_labels_and_prior_refs():
    from eval.persona_atoms import AtomicAnnotations,metrics
    a=AtomicAnnotations.model_validate({'dataset_kind':'synthetic','annotator':'schema test','atoms':[
        {'id':'a1','turn_id':'u1','persona_id':'p1','text':'가설','kind':'hypothesis','annotation_reason':'검토 필요'},
        {'id':'a2','turn_id':'u2','persona_id':'p1','text':'사실 주장','kind':'fact','supported':False,'annotation_reason':'근거 없음'}]})
    result=metrics(a);assert result['grounded_hypothesis_rate'] is None and result['grounded_fact_rate']==0
    raw=a.model_dump();raw['atoms'][0]['contradicts_atom_ids']=['a2']
    with pytest.raises(ValueError,match='earlier'):AtomicAnnotations.model_validate(raw)

def test_question_and_finish_failure_resume_do_not_duplicate(tmp_path):
    class Fail(LLMClient):
        def __init__(self): super().__init__('mock'); self.fail_at=None; self.interacts=0;self.posts=0;self.fail_post_at=None
        def call(self,task,*args,**kw):
            if task in ('interact','chat'):
                self.interacts+=1
                if self.interacts==self.fail_at: raise LLMError('deliberate interruption')
            if task=='agent' and args[0].get('phase')=='post':
                self.posts+=1
                if self.posts==self.fail_post_at:raise LLMError('deliberate post interruption')
            return super().call(task,*args,**kw)
    llm=Fail(); api,_,s=prepared(tmp_path,llm); base=f'/api/sessions/{s["id"]}'
    api.post(base+'/start',json={}); llm.fail_at=2
    q={'question':'역할의 조건 비교','interaction':'interactive'}
    assert api.post(base+'/ask',json=q).status_code==502
    partial=api.get(base).json(); ids=[t['id'] for t in partial['transcript']]
    assert api.post(base+'/ask',json={'question':'다른 질문'}).status_code==502
    assert api.post(base+'/finish',json={}).status_code==502
    final=api.post(base+'/ask',json=q).json()
    assert [t['id'] for t in final['transcript'][:len(ids)]]==ids and len(final['threads'])==1
    llm.fail_post_at=2
    assert api.post(base+'/finish',json={}).status_code==502
    count=len(api.get(base).json()['transcript'])
    final=api.post(base+'/finish',json={}).json()
    assert final['status']=='COMPLETE'
    assert not any(t['round']=='Closing check' for t in final['transcript'])
    assert sum(t['phase']=='post' for t in final['transcript'])==3
    assert len(final['transcript'])>count

def test_unsupported_experience_and_purchase_guard_preserves_raw(tmp_path):
    api,_,s=prepared(tmp_path); session=Session.model_validate(s)
    class Overclaim(LLMClient):
        def call(self,*args,**kw): return AgentAnswer(content='직접 경험했고 구매하겠습니다.',stance='positive')
    a=PersonaAgent(session.cards[0],Overclaim('mock')).answer(session.brief,'pre','Private Pre','구매?')
    assert a.quality_flags==['purchase_overclaim'] and a.generated_content=='직접 경험했고 구매하겠습니다.'
    assert a.stance=='conditional' and '구매하겠습니다' not in a.content

def test_long_chat_has_bounded_threads_without_session_public_ceiling(tmp_path):
    api,_,s=prepared(tmp_path,n=1); base=f'/api/sessions/{s["id"]}'
    s=api.post(base+'/start',json={}).json(); model=Session.model_validate(s)
    for n in range(59): model.transcript.append(Utterance(id=f'g{n}',persona_id='p1',phase='group',round='old',question='q',content='조건 미확인'))
    api.app.state.store.put(model)
    reply=api.post(base+'/ask',json={'question':'추가?'});assert reply.status_code==200,reply.text
    assert 1<=len(reply.json()['threads'][-1]['utterance_ids'])<=5
    assert api.post(base+'/ask',json={'question':'또 다른 조건?'}).status_code==200
    final=api.post(base+'/finish',json={}).json()
    assert final['status']=='COMPLETE' and sum(t['phase']=='group' for t in final['transcript'])>=61

def test_repeated_response_retries_once_and_keeps_original(tmp_path):
    from backend.schemas import InteractionAnswer
    _,_,s=prepared(tmp_path); model=Session.model_validate(s)
    repeated='기관 간 협력 현황을 확인해야 합니다. 다른 역할에서도 같은 불확실성이 남아 있습니다.'
    class Repeating(LLMClient):
        def __init__(self):super().__init__('qwen');self.payloads=[]
        def call(self,task,payload,schema,**kw):
            self.payloads.append(payload)
            return InteractionAnswer(content=repeated if len(self.payloads)==1 else '가설로는 기관 도입의 준비 시간을 줄일 수 있는지 먼저 비교하겠습니다.',reasoning_rule_ids=['r1'])
    llm=Repeating(); agent=PersonaAgent(model.cards[0],llm)
    agent.context.add({'id':'u1','persona_id':'p1','phase':'group','content':repeated})
    core=fingerprint(agent.card)
    a=agent.answer(model.brief,'group','Founder Follow-up','가격은?',interaction=True,participants=['p1'],dialogue_goal='가격 판단 조건')
    assert len(llm.payloads)==2 and llm.payloads[-1]['dialogue_goal']=='가격 판단 조건'
    assert a.generated_content==repeated and a.quality_flags==['response_repetition_repaired']
    assert fingerprint(agent.card)==core

def test_closing_and_post_keep_own_conditions_and_private_baseline(tmp_path):
    class Trace(LLMClient):
        def __init__(self):super().__init__('mock');self.payloads=[]
        def call(self,task,payload,schema,**kw):
            if task in ('agent','interact','chat'):self.payloads.append(payload)
            return super().call(task,payload,schema,**kw)
    trace=Trace();api,_,s=prepared(tmp_path,trace);base=f'/api/sessions/{s["id"]}'
    api.post(base+'/start',json={});api.post(base+'/ask',json={'question':'조건 비교','interaction':'interactive'})
    final=api.post(base+'/finish',json={}).json()
    closing=[p for p in trace.payloads if p['round']=='Closing check']
    assert all(not p['group']['recent'] and p['dialogue_goal']==p['question'] for p in closing)
    assert all(t['dialogue_act']=='close' and not t['followup_question'] for t in final['transcript'] if t['round']=='Closing check')
    for p in [p for p in trace.payloads if p['phase']=='post']:
        pre=next(t for t in final['transcript'] if t['phase']=='pre' and t['persona_id']==p['card']['id'])
        assert p['private_baseline']['content']==pre['content']
        assert all(t['round']!='Closing check' and t['persona_id']!=p['card']['id'] for t in p['group']['recent'])
