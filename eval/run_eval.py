import argparse,csv,json,statistics
from pathlib import Path
from collections import Counter
from backend.llm import LLMClient
from backend.context import PersonaAgent
from backend.services import parse_idea
from .schema import AXES,EvalCase,JudgeScores,PairChoice
from .metrics import metrics

ROOT=Path(__file__).resolve().parents[1]

def aggregate(judges):
    result={}
    for axis in AXES:
        vals=[j.scores[axis].score for j in judges if j.scores[axis].score is not None]
        count=Counter(vals); winner,n=count.most_common(1)[0] if vals else (None,0)
        majority=n>len(judges)/2
        result[axis]={'score':winner if majority else statistics.median(vals) if vals else None,
                      'majority':majority,'raw':vals,'rationales':[j.scores[axis].rationale for j in judges]}
    return result

def judge(case,candidate,client,count=1):
    rubric=(ROOT/'docs/04_PSV9_EVALUATION.md').read_text(encoding='utf-8')
    payload={'case':case.model_dump(mode='json'),'candidate':candidate,'axes':AXES,'rubric':rubric}
    return aggregate([client.call('judge',payload,JudgeScores,max_tokens=1500,seed=100+i) for i in range(count)])

def compare_pair(case,a,b,client,count=1):
    rubric=(ROOT/'docs/04_PSV9_EVALUATION.md').read_text(encoding='utf-8')
    votes=[]; raw=[]
    for swapped in (False,True):
        for j in range(count):
            p={'case':case,'rubric':rubric,'A':b if swapped else a,'B':a if swapped else b}
            r=client.call('pair',p,PairChoice,max_tokens=400,seed=200+j)
            remap={'A':'B','B':'A','tie':'tie'} if swapped else {'A':'A','B':'B','tie':'tie'}
            votes.append(remap[r.winner]); raw.append({'swapped':swapped,**r.model_dump(),'mapped':remap[r.winner]})
    counts=Counter(votes); top,n=counts.most_common(1)[0]
    return {'winner':top if n>len(votes)/2 else 'tie','votes':votes,'raw':raw}

def run(dataset,out,mode='mock',judges=1,swap=False,candidate_file=None):
    if judges not in (1,3): raise ValueError('use one or three judges')
    out=Path(out); out.mkdir(parents=True,exist_ok=True); llm=LLMClient(mode=mode)
    cases=[EvalCase.model_validate_json(l) for l in Path(dataset).read_text(encoding='utf-8').splitlines() if l.strip()]
    saved={r['case_id']:r['candidate'] for r in [json.loads(l) for l in Path(candidate_file).read_text(encoding='utf-8').splitlines() if l.strip()]} if candidate_file else {}
    results=[]; candidates=[]
    for case in cases:
        if candidate_file:
            if case.case_id not in saved: raise ValueError('missing saved candidate '+case.case_id)
            from backend.schemas import AgentAnswer
            candidate=AgentAnswer.model_validate(saved[case.case_id]).model_dump(mode='json')
        else:
            agent=PersonaAgent(case.card,llm)
            for h in case.history:
                if h.get('persona_id')==case.card.id: agent.context.add(h)
            candidate=agent.answer(parse_idea(case.idea),'independent','Evaluation',case.question,max_tokens=500).model_dump(mode='json')
        candidates.append({'case_id':case.case_id,'dataset_kind':case.dataset_kind,'candidate':candidate})
        scores=judge(case,candidate,llm,judges)
        pair=compare_pair(case.model_dump(mode='json'),candidate,case.gold_response,llm,judges) if swap and case.gold_response else None
        results.append({'case_id':case.case_id,'dataset_kind':case.dataset_kind,'scores':scores,'pair_vs_gold':pair,
                        'metrics':metrics(case.human_annotations) if case.human_annotations else None})
    for name,rows in [('candidates.jsonl',candidates),('judge_scores.jsonl',results)]:
        (out/name).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    with (out/'scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['case_id','dataset_kind']+AXES)
        for r in results: w.writerow([r['case_id'],r['dataset_kind']]+[r['scores'][a]['score'] for a in AXES])
    summary={'cases':len(results),'synthetic_cases':sum(r['dataset_kind']=='synthetic' for r in results),'judges':judges,
             'means':{a:statistics.mean(v) if (v:=[r['scores'][a]['score'] for r in results if r['scores'][a]['score'] is not None]) else None for a in AXES},
             'usage':llm.usage(),'notice':'Smoke only when mock or synthetic; no real performance validation.'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--dataset',default='eval/data/synthetic_demo.jsonl'); p.add_argument('--out',default='eval/runs/demo')
    p.add_argument('--mode',choices=['mock','qwen'],default='mock'); p.add_argument('--judges',type=int,choices=[1,3],default=1)
    p.add_argument('--swap',action='store_true'); p.add_argument('--candidates')
    a=p.parse_args(); print(json.dumps(run(a.dataset,a.out,a.mode,a.judges,a.swap,a.candidates),ensure_ascii=False,indent=2))
