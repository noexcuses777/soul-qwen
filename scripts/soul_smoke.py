"""A NEW synthetic session; never reads latest/deletes/reuses user interviews."""
import argparse,json,time
from pathlib import Path
import httpx

def run(base_url,prepared_session=None):
    start=time.perf_counter()
    with httpx.Client(base_url=base_url.rstrip('/'),timeout=1800) as c:
        def request(method,path,payload=None):
            r=c.request(method,path,json=payload); r.raise_for_status(); return r.json()
        health=request('GET','/api/health')
        assert health['status']=='ok',health
        demo={'q1':'독립 서점의 소규모 행사 예약과 대기자 관리를 돕는 서비스',
            'q2':'전화와 메시지로 신청을 받아 정원을 조정하는 과정을 줄이고 싶습니다.',
            'q3_1':'소규모 운영자가 예약과 취소를 한 화면에서 확인하도록 돕습니다.',
            'q3_2':'사용량에 따른 구독 요금은 실제 인터뷰로 검토할 계획입니다.',
            'q4_1':'웹 기반 예약 페이지와 운영자 대시보드로 시작하려 합니다.','q5':'IT'}
        s=request('GET',f'/api/sessions/{prepared_session}') if prepared_session else request('POST','/api/sessions',demo)
        assert s['input']['q1']==demo['q1'] and s['status']=='CREATED' and not s['transcript'], 'Only a newly created synthetic smoke session may resume.'
        sid=s['id']; targets=s['targets']
        # The six-to-eight raw proposals are deduplicated by contrast signature.
        assert 3<=len(targets)<=8 and not s['cards']
        s=request('POST',f'/api/sessions/{sid}/select',{'target_ids':[t['id'] for t in targets[:3]]})
        assert len(s['cards'])==3 and all(not v['issues'] for v in s['validations'])
        core=[x['immutable_core'] for x in s['cards']]
        s=request('POST',f'/api/sessions/{sid}/ask',{'question':'현재 대안과 비교해 어떤 조건에서 도움이 될지 각자 판단하고 서로 다른 조건을 확인해 주세요.','interaction':'auto'})
        group=[t for t in s['transcript'] if t['phase']=='group']
        assert {t['persona_id'] for t in group}=={p['id'] for p in s['cards']}
        assert len(group)>=len(s['cards'])
        s=request('POST',f'/api/sessions/{sid}/finish',{})
        view=request('GET',f'/api/sessions/{sid}/report-view')
        assert s['report'] and len(s['report']['sections'])==8
        assert [x['immutable_core'] for x in s['cards']]==core
        # The presenter is a view of the report snapshot, not another model call.
        saved=request('GET',f'/api/sessions/{sid}')
        cached=request('POST',f'/api/sessions/{sid}/finish',{})
        assert cached['report']==saved['report']
        return {'dataset_kind':'synthetic','mode':health['mode'],'session_id':sid,
            'model':health['model'],'targets':len(targets),'personas':len(s['cards']),
            'public_utterances':len(group),'report_sections':len(s['report']['sections']),
            'report_view_keys':list(view),'immutable_core_preserved':True,
            'same_revision_report_cached':True,'elapsed_s':round(time.perf_counter()-start,3),
            'quality_claim':'Execution smoke only; no human quality or market validation.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--base-url',default='http://127.0.0.1:8000'); p.add_argument('--out'); p.add_argument('--prepared-session',help='Explicit ID of this synthetic demo in CREATED state only'); a=p.parse_args()
    result=run(a.base_url,a.prepared_session)
    if a.out:
        target=Path(a.out); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
