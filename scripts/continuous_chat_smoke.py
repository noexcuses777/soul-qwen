"""Protocol-5 API checks. Real inference and synthetic controller tests are distinct."""
import argparse, json, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient
from backend.schemas import Session
from backend.context import fingerprint
from eval.conversation_metrics import structural_metrics

def main():
    p=argparse.ArgumentParser(); p.add_argument('--mode',choices=['mock','qwen'],default='mock')
    p.add_argument('--out',default='examples/continuous_chat_demo'); p.add_argument('--prepared')
    p.add_argument('--idea',default='examples/idea.json'); a=p.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    llm=LLMClient(a.mode); api=TestClient(create_app(str(out/'smoke.sqlite3'),llm)); timer=time.perf_counter()
    s=None; stages=[]
    def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def step(path,payload,label):
        nonlocal s
        print(label,flush=True); start=len(llm.records); t=time.perf_counter(); r=api.post(path,json=payload)
        stages.append({'stage':label,'http':r.status_code,'latency_s':round(time.perf_counter()-t,3),'usage':llm.usage(start)})
        if r.status_code!=200:
            if s: save('session.json',api.get(f'/api/sessions/{s["id"]}').json())
            save('failed_call.json',{'stage':label,'http':r.status_code,'detail':r.json(),'usage':llm.usage()})
            raise RuntimeError(r.text[:2000])
        s=r.json(); save('session.json',s); save(label+'.json',s)
    if a.prepared:
        src=Session.model_validate_json(Path(a.prepared).read_text(encoding='utf-8'))
        s=Session(id='v5-'+uuid.uuid4().hex[:12],input=src.input,brief=src.brief,targets=src.targets,
            cards=src.cards,validations=src.validations,status='SELECTED',mode=a.mode,protocol_version='5').model_dump(mode='json')
        for c in s['cards']: c['session_state']={'stance':'unknown','reasons':[],'unresolved_issues':[],'revisions':[]}
        api.app.state.store.put(Session.model_validate(s)); save('00_prepared_cards.json',s)
    else:
        step('/api/sessions',json.loads(Path(a.idea).read_text(encoding='utf-8')),'01_targets')
        step(f'/api/sessions/{s["id"]}/select',{'target_ids':[t['id'] for t in s['targets'][:3]]},'02_personas')
    base=f'/api/sessions/{s["id"]}'; hashes=[fingerprint(c) for c in Session.model_validate(s).cards]
    questions=[
        '기존 대안과 비교해 유료 서비스로 바꾸려면 어떤 가치와 비용 조건을 확인해야 하나요? 각자 판단 이유와 서로 다른 조건을 비교해 주세요.',
        '앞서 나온 준비 노력과 신뢰 문제를 구분하면, 작은 PoC를 어떤 방식으로 진행하고 무엇을 확인해야 판단이 바뀔까요?',
        '사업 초기에는 개인 구독과 기관 라이선스 중 무엇부터 검토하면 좋을까요? 자기 역할과 현재 대안에 근거해 상충 조건을 비교해 주세요.']
    for i,q in enumerate(questions):
        before=sum(t['phase']=='group' for t in s['transcript'])
        step(base+'/ask',{'question':q,'interaction':'interactive'},f'0{i+3}_message')
        ids=set(s['threads'][-1]['utterance_ids']); turns=[t for t in s['transcript'] if t['id'] in ids]
        assert {t['persona_id'] for t in turns}=={c['id'] for c in s['cards']}
        assert 6<=len(turns)<=9 and not any(r['task']=='report' for r in stages[-1]['usage']['records'])
        assert sum(t['phase']=='group' for t in s['transcript'])>before
        if i==1:
            step(base+'/finish',{},'06_snapshot')
            snapshot=json.loads(json.dumps(s['report'])); old_revision=s['report_revision']
        if i==2: assert s['report']==snapshot and s['report_stale'] and s['report_revision']==old_revision
    step(base+'/finish',{},'07_snapshot_refresh')
    calls=len(llm.records); transcript=s['transcript']; step(base+'/finish',{},'08_cached_snapshot')
    assert len(llm.records)==calls and s['transcript']==transcript and not s['report_stale']
    assert hashes==[fingerprint(c) for c in Session.model_validate(s).cards]
    structure=structural_metrics(Session.model_validate(s)); assert not structure['invalid_reply_ids']
    result={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'mode':a.mode,'prepared_cards_from':a.prepared,
        'cards_generated_this_run':not bool(a.prepared),'model_health':llm.health(),'elapsed_seconds':round(time.perf_counter()-timer,3),
        'stages':stages,'usage':llm.usage(),'status':s['status'],'public_turns':sum(t['phase']=='group' for t in s['transcript']),
        'thread_turn_counts':[len(t['utterance_ids']) for t in s['threads']], 'report_revision':s['report_revision'],
        'report_sections':list(s['report']['sections']),'structure':structure,
        'notice':'Synthetic controller smoke; no semantic performance claim' if a.mode=='mock' else 'Real Qwen inference; no human/market validity claim'}
    save('verification.json',result); print(json.dumps({k:result[k] for k in ('mode','status','elapsed_seconds','thread_turn_counts','public_turns','report_revision')},ensure_ascii=False),flush=True)
if __name__=='__main__': main()
