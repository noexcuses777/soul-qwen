"""Exercise real Qwen or explicitly synthetic guided API, saving every completed stage."""
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient
from backend.schemas import Session
from eval.conversation_metrics import structural_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['mock','qwen'],default='mock')
    p.add_argument('--out',default='examples/guided_demo');p.add_argument('--resume')
    p.add_argument('--idea',default='examples/idea.json');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    llm=LLMClient(a.mode);api=TestClient(create_app(str(out/'smoke.sqlite3'),llm));start=time.perf_counter()
    s=None
    def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def step(endpoint,payload,label):
        nonlocal s
        print(label,flush=True);r=api.post(endpoint,json=payload)
        if r.status_code!=200:
            if s: save('session.json',api.get(f'/api/sessions/{s["id"]}').json())
            save('failed_call.json',{'stage':label,'http':r.status_code,'detail':r.json(),'usage':llm.usage()})
            raise RuntimeError(f'{label}: {r.text[:1800]}')
        s=r.json();save('session.json',s);save(label.split()[0].strip('[]')+'.json',s)
    if a.resume:
        s=json.loads(Path(a.resume).read_text(encoding='utf-8'));api.app.state.store.put(Session.model_validate(s))
    else: step('/api/sessions',json.loads(Path(a.idea).read_text(encoding='utf-8')),'[01] targets')
    base=f'/api/sessions/{s["id"]}'
    if not s['cards']:step(base+'/select',{'target_ids':[t['id'] for t in s['targets'][:3]]},'[02] personas and independent validators')
    if not s['suggestions']:step(base+'/suggestions',{},'[03] Qwen question plan')
    if s['status'] in ('SELECTED','FAILED','PRE'):step(base+'/start',{'mode':'guided'},'[04] private pre and user turn')
    questions=['제안한 방식이 각자의 역할에서 도움이 되려면 어떤 조건이 필요하고, 다른 참여자의 조건과 무엇이 다른가요?',
               '현재 대안에서 바꾸려면 어떤 확인이 먼저 필요한가요? 이미 경험했거나 구매할 것처럼 단정하지 말고 서로의 조건을 비교해주세요.']
    if s['status']=='WAITING':
        for n,q in enumerate(questions):
            if len(s['threads'])>n and (s['dialogue_runtime'].get('followup',{}).get('done') or n<len(s['threads'])-1): continue
            step(base+'/ask',{'question':q,'interaction':'interactive'},f'[{5+n:02}] interactive question {n+1}')
    if s['status']!='COMPLETE':step(base+'/finish',{},'[07] closing private post report')
    result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'mode':a.mode,'resumed_from':a.resume,
        'elapsed_seconds':round(time.perf_counter()-start,3),'elapsed_scope':'this invocation only',
        'model_health':llm.health(),'usage':llm.usage(),'status':s['status'],
        'persona_names':[c['presentation']['display_name'] for c in s['cards']],
        'reasoning_rules_per_card':[len(c['immutable_core']['reasoning_rules']) for c in s['cards']],
        'blocking_validator_issues':[len(v['issues']) for v in s['validations']],
        'suggestion_count':len(s['suggestions']),'report_sections':list(s['report']['sections']),
        'structure':structural_metrics(Session.model_validate(s)),
        'notice':'Synthetic execution only' if a.mode=='mock' else 'Real local model execution; human semantic/market validity unverified'}
    save('verification.json',result)
    assert s['status']=='COMPLETE' and len(s['cards'])==3 and len(s['threads'])==2
    assert not result['structure']['invalid_reply_ids']
    print(json.dumps({k:v for k,v in result.items() if k not in ('usage','structure')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
