import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient,LLMError
from backend.prompts import ROUNDS

def setup(tmp_path,llm,n=3):
    api=TestClient(create_app(str(tmp_path/'adaptive.db'),llm))
    s=api.post('/api/sessions',json={'q1':'고객 인터뷰 준비 도구','q5':'IT'}).json()
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'target_ids':[f't{i+1}' for i in range(n)]})
    assert r.status_code==200,r.text
    return api,s['id']

@pytest.mark.parametrize('n',[1,2,3])
def test_adaptive_coverage_budget_recipient_and_private_isolation(tmp_path,n):
    class Capture(LLMClient):
        def __init__(self): super().__init__('mock'); self.payloads=[]
        def call(self,task,payload,schema,**kw):
            if task in ('agent','interact','chat'): self.payloads.append(payload)
            return super().call(task,payload,schema,**kw)
    llm=Capture();api,id=setup(tmp_path,llm,n)
    r=api.post(f'/api/sessions/{id}/run',json={});assert r.status_code==200,r.text
    s=r.json();group=[t for t in s['transcript'] if t['phase']=='group'];lookup={t['id']:t for t in s['transcript']}
    assert s['status']=='COMPLETE' and len(group)<=18
    assert {x[0] for x in ROUNDS}<={t['round'] for t in group}
    assert len([t for t in group if t['round']=='Closing check'])==n
    for t in group:
        if t['reply_to']:
            prev=lookup[t['reply_to']]
            assert prev['phase']=='group' and prev['persona_id']!=t['persona_id']
            if prev['addressed_to'] and t['question'].startswith(prev['persona_id']+'님의 공개 발화'): assert prev['addressed_to']==t['persona_id']
    for p in llm.payloads:
        assert all(x['persona_id']==p['card']['id'] for x in p['own']['recent'])
        assert all(x['phase']=='group' for x in p['group']['recent'])
        if p['phase']=='pre':assert not p['group']['recent']
    if n>1:assert any(t['reply_to'] for t in group)
    assert {t['persona_id'] for t in group if t['round']!='Closing check'}=={f'p{i+1}' for i in range(n)}

def test_content_changes_length_and_followup_modes(tmp_path):
    class Enough(LLMClient):
        def call(self,task,payload,schema,**kw):
            a=super().call(task,payload,schema,**kw)
            if task in ('interact','chat'):
                a.dialogue_act='answer';a.stance='unknown';a.addressed_to=None;a.followup_question='';a.unresolved_issues=[]
            return a
    api,id=setup(tmp_path,Enough('mock'))
    s=api.post(f'/api/sessions/{id}/run',json={}).json()
    assert len([t for t in s['transcript'] if t['phase']=='group'])==9 # Early completion, no forced debate.
    for mode in ('direct','auto','interactive'):
        before=len(s['transcript'])
        r=api.post(f'/api/sessions/{id}/ask',json={'question':'도입 조건을 확인해주세요.','persona_id':'p2','interaction':mode})
        assert r.status_code==200,r.text
        s=r.json();added=s['transcript'][before:]
        assert (len(added)==1 if mode=='direct' else 6<=len(added)<=15)
        assert added[0]['persona_id']=='p2'
        if mode!='direct': assert {t['persona_id'] for t in added}=={'p1','p2','p3'}
        assert all(t['dialogue_act']=='answer' for t in added)
        assert s['status']=='WAITING' and s['protocol_version']=='6'
        if mode!='direct':
            assert {t['persona_id'] for t in added}=={'p1','p2','p3'}
            assert any(t['reply_to'] for t in added)

def test_adaptive_and_followup_failure_resume(tmp_path):
    class FailOnce(LLMClient):
        def __init__(self):super().__init__('mock');self.n=0;self.fail_at=4
        def call(self,task,*args,**kw):
            if task in ('interact','chat'):
                self.n+=1
                if self.n==self.fail_at:raise LLMError('transient')
            return super().call(task,*args,**kw)
    llm=FailOnce();api,id=setup(tmp_path,llm)
    assert api.post(f'/api/sessions/{id}/run',json={}).status_code==502
    before=api.get(f'/api/sessions/{id}').json()['transcript']
    s=api.post(f'/api/sessions/{id}/run',json={}).json()
    assert s['status']=='COMPLETE' and s['transcript'][:len(before)]==before
    llm.fail_at=llm.n+2
    q={'question':'다른 역할과 도입 조건을 비교해주세요.','persona_id':'p1','interaction':'interactive'}
    assert api.post(f'/api/sessions/{id}/ask',json=q).status_code==502
    saved=api.get(f'/api/sessions/{id}').json()
    assert saved['error']=='transient' and saved['dialogue_runtime']['followup']['count']==1
    wrong=api.post(f'/api/sessions/{id}/ask',json={**q,'question':'다른 질문'})
    assert wrong.status_code==502
    r=api.post(f'/api/sessions/{id}/ask',json=q);assert r.status_code==200,r.text
    s=r.json();assert s['error'] is None and s['transcript'][:len(saved['transcript'])]==saved['transcript']
    assert len({t['id'] for t in s['transcript']})==len(s['transcript'])
    assert s['dialogue_runtime']['followup']['done']

def test_long_followups_keep_report_bounded_without_losing_transcript(tmp_path):
    api,id=setup(tmp_path,LLMClient('mock'))
    s=api.post(f'/api/sessions/{id}/run',json={}).json();initial=list(s['transcript'])
    for i in range(20):
        r=api.post(f'/api/sessions/{id}/ask',json={'question':f'{i}번째 조건을 확인해주세요.','interaction':'direct'})
        assert r.status_code==200,r.text
    s=r.json()
    assert len(s['transcript'])==len(initial)+20 and s['transcript'][:len(initial)]==initial
    assert s['report_stale'] is True
    s=api.post(f'/api/sessions/{id}/finish',json={}).json()
    assert s['status']=='COMPLETE' and s['report_stale'] is False
    assert '최근 공개 발화' in s['report']['notice']

def test_repeated_questions_do_not_loop():
    from backend.adaptive import AdaptiveConversation
    assert AdaptiveConversation.repeated_question('비용 효율성 데이터 출처는 어디인가요?','비용 효율성 데이터 출처는 어디인가요.')
    assert not AdaptiveConversation.repeated_question('누가 도입을 결정하나요?','구체적인 전환 비용은 얼마인가요?')

def test_agenda_order_responds_to_current_issue(tmp_path):
    from backend.adaptive import AdaptiveConversation
    from backend.orchestrator import TurnController
    from backend.schemas import Utterance
    llm=LLMClient('mock');api,id=setup(tmp_path,llm)
    engine=AdaptiveConversation(llm,TurnController());engine.restore(api.app.state.store.get(id))
    for agent in engine.agents.values(): agent.state.unresolved_issues=[]
    engine.public.add(Utterance(id='u1',persona_id='p1',phase='group',round='Problem Reality',question='문제?',content='도입 가격과 예산, 지불하는 사람이 궁금합니다.'))
    assert engine.next_topic({'topic':1,'visited':[0]})==4
    engine.public=type(engine.public)()
    engine.public.add(Utterance(id='u2',persona_id='p1',phase='group',round='Problem Reality',question='문제?',content='이 도구를 포기하거나 사용을 중단하는 실패 조건을 확인하고 싶습니다.'))
    assert engine.next_topic({'topic':1,'visited':[0]})==5
