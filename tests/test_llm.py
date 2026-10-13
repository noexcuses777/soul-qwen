import httpx,pytest
from backend.llm import LLMClient,LLMError
from backend.schemas import AgentAnswer

def test_qwen_http_contract_and_repair():
    calls=[]
    def handler(req):
        if req.url.path in ('/props','/apply-template'): return httpx.Response(404)
        if req.url.path=='/tokenize': return httpx.Response(200,json={'tokens':[1]*100})
        calls.append(req)
        content='bad json' if len(calls)==1 else '{"content":"모릅니다"}'
        return httpx.Response(200,json={'choices':[{'message':{'content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':20}})
    c=LLMClient('qwen',transport=httpx.MockTransport(handler));r=c.call('agent',{},AgentAnswer)
    assert r.content=='모릅니다' and len(calls)==2 and c.usage()['completion_tokens']==40
    import json
    body=json.loads(calls[0].content);assert body['response_format']['type']=='json_schema' and not body['chat_template_kwargs']['enable_thinking']

def test_transport_and_invalid_fail():
    c=LLMClient('qwen',transport=httpx.MockTransport(lambda req:httpx.Response(503)))
    with pytest.raises(LLMError,match='transport'): c.call('agent',{},AgentAnswer)
    def handler(req):
        if req.url.path=='/tokenize': return httpx.Response(200,json={'tokens':[1]*10})
        return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
    with pytest.raises(LLMError,match='invalid JSON'): LLMClient('qwen',transport=httpx.MockTransport(handler)).call('agent',{},AgentAnswer)
    with pytest.raises(ValueError,match='local'): LLMClient('qwen',base_url='https://external.example/v1')

def test_context_guard():
    c=LLMClient('qwen',context_size=128,transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'tokens':[1]*200})))
    with pytest.raises(LLMError,match='Context'): c.call('agent',{},AgentAnswer)

def test_report_grammar_requires_nonempty_valid_utterance_reference():
    import json
    from backend.schemas import Report,SECTIONS
    bodies=[]
    def handler(req):
        if req.url.path in ('/props','/apply-template'):return httpx.Response(404)
        if req.url.path=='/tokenize':return httpx.Response(200,json={'tokens':[1]*100})
        bodies.append(json.loads(req.content))
        report={'sections':{name:[{'text':'가설','utterance_ids':['u1']}] for name in SECTIONS}}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(report)}}]})
    LLMClient('qwen',transport=httpx.MockTransport(handler)).call('report',{'transcript':['u1|p1|pre: 조건 미확인']},Report)
    insight=bodies[0]['response_format']['json_schema']['schema']['$defs']['Insight']
    assert 'utterance_ids' in insight['required']
    assert insight['properties']['utterance_ids']['minItems']==1
    assert insight['properties']['utterance_ids']['items']['enum']==['u1']

def test_qwen_health_reports_real_connection_state():
    def handler(req):
        if req.url.path=='/health': return httpx.Response(200,json={'status':'ok'})
        if req.url.path=='/v1/models': return httpx.Response(200,json={'data':[{'id':'persona-qwen'}]})
        return httpx.Response(404)
    c=LLMClient('qwen',transport=httpx.MockTransport(handler))
    health=c.health()
    assert health['connected'] and health['available_models']==['persona-qwen']
    offline=LLMClient('qwen',transport=httpx.MockTransport(lambda req:httpx.Response(503))).health()
    assert not offline['connected']

def test_api_reports_disconnected_qwen_before_generation(tmp_path):
    from backend.app import create_app
    from fastapi.testclient import TestClient
    llm=LLMClient('qwen',transport=httpx.MockTransport(lambda req:httpx.Response(503)))
    response=TestClient(create_app(str(tmp_path/'offline.db'),llm)).post('/api/sessions',json={'q1':'idea','q5':'IT'})
    assert response.status_code==503 and 'Qwen 모델 서버 연결이 끊겼습니다' in response.json()['detail']

def test_http_protocol_full_flow(tmp_path):
    import json
    from backend.mock import fixture
    from backend.prompts import PROMPTS
    from backend.app import create_app
    from fastapi.testclient import TestClient
    def handler(req):
        if req.url.path=='/health': return httpx.Response(200,json={'status':'ok'})
        if req.url.path=='/v1/models': return httpx.Response(200,json={'data':[{'id':'persona-qwen'}]})
        if req.url.path=='/tokenize':return httpx.Response(200,json={'tokens':[1]*100})
        if req.url.path in ('/props','/apply-template'):return httpx.Response(404)
        body=json.loads(req.content)
        task=next(k for k,v in sorted(PROMPTS.items(),key=lambda kv:-len(kv[1])) if v in body['messages'][0]['content'])
        payload=json.loads(body['messages'][1]['content'])
        data=fixture(task,payload)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data)}}],
                                      'usage':{'prompt_tokens':100,'completion_tokens':120}})
    llm=LLMClient('qwen',transport=httpx.MockTransport(handler))
    api=TestClient(create_app(str(tmp_path/'http.db'),llm));s=api.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json()
    assert s['mode']=='qwen'
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'target_ids':['t1','t2','t3']});assert r.status_code==200
    r=api.post(f'/api/sessions/{s["id"]}/run',json={});assert r.status_code==200
    s=r.json()
    # A detected repeated closing response may incur ONE extra candidate call per participant.
    assert s['status']=='COMPLETE' and len(s['transcript'])+8<=len(llm.records)<=len(s['transcript'])+8+len(s['cards'])
    assert any('response_repeat_unresolved' in t['quality_flags'] for t in s['transcript'])
    assert llm.usage()['completion_tokens']==len(llm.records)*120
