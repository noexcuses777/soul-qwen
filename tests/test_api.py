import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient,LLMError

def test_api_e2e_persistence(tmp_path):
    db=str(tmp_path/'s.db');c=TestClient(create_app(db,LLMClient('mock')))
    assert c.get('/').status_code==200 and c.get('/assets/app.js').status_code==200
    assert c.get('/api/health').json()['mode']=='mock'
    assert c.post('/api/sessions',json={'q1':'idea'}).status_code==422
    s=c.post('/api/sessions',json={'q1':'test idea','q5':'IT'}).json();id=s['id']
    assert c.post(f'/api/sessions/{id}/run',json={}).status_code==409
    assert c.post(f'/api/sessions/{id}/select',json={'target_ids':['fake']}).status_code==422
    assert c.post(f'/api/sessions/{id}/select',json={'target_ids':['t1','t2','t3']}).status_code==200
    s=c.post(f'/api/sessions/{id}/run',json={}).json()
    assert s['status']=='COMPLETE' and 9<=sum(t['phase']=='group' for t in s['transcript'])<=18
    assert s['protocol_version']=='3' and s['chat_events']
    c2=TestClient(create_app(db,LLMClient('mock')))
    assert c2.get(f'/api/sessions/{id}').json()['report']==s['report']
    assert c2.post(f'/api/sessions/{id}/run',json={}).status_code==409
    r=c2.post(f'/api/sessions/{id}/calibrate',json={'dataset_kind':'human','predicted_themes':['x'],'real_themes':['x','y']})
    assert r.status_code==200 and r.json()['theme_recall']==.5
    assert c2.post(f'/api/sessions/{id}/calibrate',json={'real_themes':'wrong'}).status_code==422
    assert c2.delete(f'/api/sessions/{id}').json()['deleted']
    assert c2.get(f'/api/sessions/{id}').status_code==404

def test_custom_selection(tmp_path):
    c=TestClient(create_app(str(tmp_path/'s.db'),LLMClient('mock')))
    s=c.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json()
    r=c.post(f'/api/sessions/{s["id"]}/select',json={'custom_targets':[{'segment_name':'기관 결정자','why_relevant':'기관 구매','buying_role':'결정자','problem_exposure':'기관 운영'}]})
    assert r.status_code==200 and r.json()['cards'][0]['immutable_core']['identity_context']['segment']=='기관 결정자'

def test_failure_persisted(tmp_path):
    class Fail(LLMClient):
        def call(self,task,*args,**kw):
            if task=='agent': raise LLMError('server unavailable')
            return super().call(task,*args,**kw)
    c=TestClient(create_app(str(tmp_path/'s.db'),Fail('mock')))
    s=c.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json();id=s['id']
    c.post(f'/api/sessions/{id}/select',json={'target_ids':['t1']})
    assert c.post(f'/api/sessions/{id}/run',json={}).status_code==502
    s=c.get(f'/api/sessions/{id}').json();assert s['status']=='FAILED' and s['report'] is None
