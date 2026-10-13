"""Real llama.cpp tokenizer + synthetic responses: budget check, NOT inference or quality evidence."""
import argparse,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient
from backend.mock import fixture
from backend.prompts import PROMPTS
from backend.limits import LIMITS

class Probe(httpx.BaseTransport):
    def __init__(self):self.real=httpx.HTTPTransport()
    def handle_request(self,request):
        if request.url.path!='/v1/chat/completions':return self.real.handle_request(request)
        body=json.loads(request.content);task=next(k for k,v in sorted(PROMPTS.items(),key=lambda kv:-len(kv[1])) if v in body['messages'][0]['content'])
        data=fixture(task,json.loads(body['messages'][1]['content']))
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data)}}]})
    def close(self):self.real.close()

def run(out='examples/context_budget_v5.json'):
    # Varied Korean prose at exactly every new-input limit, with the maximum total evidence size.
    passage='사용자가 기존 대안을 비교하며 예산과 전환비용, 반복되는 업무 조건을 확인하는 상황이다. 실제 근거가 없다면 경험과 구매 의사는 알 수 없다. '
    at=lambda n:(passage*((n//len(passage))+1))[:n]
    idea={k:at(LIMITS[k]) for k in ('q1','q2','q3_1','q3_2','q4_1')};idea['q5']='IT'
    idea['evidence']=[{'source_id':f'e{i}','level':2,'text':at(750)} for i in range(8)]
    llm=LLMClient('qwen',transport=Probe(),context_size=8192)
    with tempfile.TemporaryDirectory() as tmp:
        api=TestClient(create_app(str(Path(tmp)/'probe.db'),llm))
        s=api.post('/api/sessions',json=idea);s.raise_for_status();id=s.json()['id']
        api.post(f'/api/sessions/{id}/select',json={'target_ids':['t1','t2','t3']}).raise_for_status()
        r=api.post(f'/api/sessions/{id}/run',json={});r.raise_for_status()
        from backend.schemas import Session
        guided=Session.model_validate(r.json()); guided.id+='-guided'; guided.protocol_version='5'; guided.status='SELECTED'
        guided.lounge_mode=None; guided.transcript=[]; guided.report=None; guided.states={}; guided.chat_events=[];guided.dialogue_runtime={}
        api.app.state.store.put(guided);base=f'/api/sessions/{guided.id}'
        api.post(base+'/ask',json={'question':at(LIMITS['question']),'interaction':'interactive'}).raise_for_status()
        final=api.post(base+'/finish',json={});final.raise_for_status()
    result={'kind':'real_tokenizer_synthetic_generation_budget_probe','not_quality_or_inference_test':True,
            'context_limit':llm.server_context(),'input_lengths':{k:len(v) for k,v in idea.items() if isinstance(v,str)},
            'evidence_total_chars':6000,'status':final.json()['status'],'protocols':['3','5'],'records':llm.records}
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'calls':len(llm.records),'largest_reserved_tokens':max(x['estimated_prompt_tokens']+x['max_tokens'] for x in llm.records),'kind':result['kind']}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='examples/context_budget_v5.json')
    run(parser.parse_args().out)
