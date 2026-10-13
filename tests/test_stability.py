import json
import httpx,pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient,LLMError
from backend.context import ContextManager,PersonaAgent
from backend.schemas import *
from backend.services import parse_idea,generate_targets,build_card,evidence_windows,validate_card
from backend.orchestrator import Orchestrator

def test_limits_reject_before_model_and_keep_legacy_readable(tmp_path):
    llm=LLMClient('mock'); api=TestClient(create_app(str(tmp_path/'limits.db'),llm))
    limits=api.get('/api/limits').json()
    for key in ('q1','q2','q3','q3_1','q3_2','q4_1','founder_strength'):
        value={'q1':'idea','q5':'IT',key:'글'*(limits[key]+1)}
        assert api.post('/api/sessions',json=value).status_code==422
    assert not llm.records
    assert api.post('/api/brief',json={'q1':'😀'*200,'q5':'IT'}).status_code==200
    assert api.post('/api/sessions',json={'q1':'idea','q5':'IT','evidence':[{'source_id':'x','text':'글'*1501,'level':3}]}).status_code==422
    assert IdeaInput(q1='old',q2='글'*6000,q5='IT').q2 # Old saved record remains readable.

def test_partial_resume_no_duplicate_turns_or_cross_private_memory(tmp_path):
    class OnceFail(LLMClient):
        def __init__(self):super().__init__('mock');self.n=0;self.payloads=[]
        def call(self,task,payload,schema,**kw):
            if task=='agent':
                self.n+=1;self.payloads.append(payload)
                if self.n==11:raise LLMError('transient interruption')
            return super().call(task,payload,schema,**kw)
    llm=OnceFail();api=TestClient(create_app(str(tmp_path/'resume.db'),llm))
    s=api.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json();id=s['id']
    legacy=api.app.state.store.get(id);legacy.protocol_version='2';api.app.state.store.put(legacy)
    api.post(f'/api/sessions/{id}/select',json={'target_ids':['t1','t2','t3']})
    assert api.post(f'/api/sessions/{id}/run',json={}).status_code==502
    saved=api.get(f'/api/sessions/{id}').json()['transcript'];assert len(saved)==10
    r=api.post(f'/api/sessions/{id}/run',json={});assert r.status_code==200,r.text
    s=r.json();assert s['status']=='COMPLETE' and len(s['transcript'])==24
    assert s['transcript'][:10]==saved and len({t['id'] for t in s['transcript']})==24
    for p in llm.payloads:
        assert all(t['persona_id']==p['card']['id'] for t in p['own']['recent'])
        if p['round'] in ('Problem Reality','Solution Reaction') or p['phase']=='pre':assert not p['group']['recent']
    assert all(t['directed_to']==t['persona_id'] and t['reply_to'] for t in s['transcript'] if t['round']=='Cross-reaction')

def test_context_packing_preserves_core_and_question():
    observed=[]
    def handler(req):
        if req.url.path=='/props':return httpx.Response(200,json={'default_generation_settings':{'n_ctx':2000},'model_path':'Qwen3.5-4B.gguf'})
        if req.url.path=='/apply-template':return httpx.Response(404)
        body=json.loads(req.content)
        if req.url.path=='/tokenize':return httpx.Response(200,json={'tokens':[1]*(len(body['content'])//2)})
        observed.append(body)
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"content":"모르는 조건을 확인해야 합니다."}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1000,'completion_tokens':50}})
    llm=LLMClient('qwen',context_size=8192,transport=httpx.MockTransport(handler))
    own=ContextManager(recent=8)
    for i in range(8):own.add({'id':f'u{i}','persona_id':'p1','phase':'group','content':'오래된 의견 '*300})
    core={'budget_constraint':'예산 상한 10만원','evidence_anchors':[{'source_id':'e1','quote':'상한 10만원'}]}
    llm.call('agent',{'card':{'id':'p1','immutable_core':core},'question':'현재 대안은?','own':own.view()},AgentAnswer,max_tokens=240)
    sent=json.loads(observed[0]['messages'][1]['content'])
    assert sent['card']['immutable_core']==core and sent['question']=='현재 대안은?'
    assert llm.records[-1]['context_compactions']>0 and llm.records[-1]['context_limit']==2000
    assert len(own.recent)==8 # Caller/source history untouched.

def test_edit_validation_and_followup(tmp_path):
    api=TestClient(create_app(str(tmp_path/'edit.db'),LLMClient('mock')))
    s=api.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json();id=s['id']
    s=api.post(f'/api/sessions/{id}/select',json={'target_ids':['t1','t2','t3']}).json()
    card=s['cards'][0];card['immutable_core']['decision_model']['budget_constraint']='10만원'
    assert api.post(f'/api/sessions/{id}/cards/p1',json=card).status_code==422
    card['immutable_core']['decision_model']['budget_constraint']='UNKNOWN'
    assert api.post(f'/api/sessions/{id}/cards/p1',json=card).status_code==200
    before=api.post(f'/api/sessions/{id}/run',json={}).json()
    r=api.post(f'/api/sessions/{id}/ask',json={'question':'실제 인터뷰에서 어떤 대안을 확인할까요?','persona_id':'p2','interaction':'direct'})
    assert r.status_code==200,r.text
    assert len(r.json()['transcript'])==len(before['transcript'])+1 and r.json()['transcript'][-1]['persona_id']=='p2'
    assert api.post(f'/api/sessions/{id}/ask',json={'question':'글'*501}).status_code==422

def test_retrieval_preserves_quotes_offsets_and_levels():
    source=Evidence(source_id='s',level=3,text='관계없는 이야기 '*70+'예산 상한은 10만원입니다.'+' 나머지 '*70)
    a=Anchor(source_id='s',level=3,field='decision_model.budget_constraint',quote='예산 상한은 10만원입니다.')
    row=evidence_windows([source],'예산 상한',[a])[0]
    assert row['anchored_quotes']==[a.quote] and row['level']==3
    for span in row['excerpts']:assert source.text[span['offset']:span['offset']+len(span['text'])]==span['text']

def test_report_grammar_requires_all_sections():
    grammar=Report.model_json_schema()['properties']['sections']
    assert set(grammar['required'])==set(SECTIONS) and not grammar['additionalProperties']
    assert set(grammar['properties'])==set(SECTIONS)
