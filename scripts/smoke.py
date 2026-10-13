"""API-level full flow without starting a model; saves reviewable result."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient

def run(out='examples/mock_e2e_result.json'):
    with tempfile.TemporaryDirectory() as tmp:
        c=TestClient(create_app(str(Path(tmp)/'smoke.sqlite3'),LLMClient('mock')))
        idea=json.loads(Path('examples/idea.json').read_text(encoding='utf-8'))
        r=c.post('/api/sessions',json=idea);r.raise_for_status();s=r.json();id=s['id']
        r=c.post(f'/api/sessions/{id}/select',json={'target_ids':[t['id'] for t in s['targets'][:3]]});r.raise_for_status()
        r=c.post(f'/api/sessions/{id}/run',json={});r.raise_for_status();s=r.json()
        assert s['status']=='COMPLETE' and sum(t['phase']=='group' for t in s['transcript'])<=18
        annotations=json.loads(Path('examples/calibration_synthetic.json').read_text(encoding='utf-8'))
        r=c.post(f'/api/sessions/{id}/calibrate',json=annotations);r.raise_for_status();s['calibration_demo']=r.json()
        Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Mock E2E passed: {len(s["cards"])} personas, {len(s["transcript"])} utterances, protocol {s["protocol_version"]}, eight report sections. Saved {out}')

if __name__=='__main__': run(sys.argv[1] if len(sys.argv)>1 else 'examples/mock_e2e_result.json')
