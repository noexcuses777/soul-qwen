"""Generate A-D under a common completion ceiling; human labels are imported separately."""
import argparse,json,random,time,statistics
from pathlib import Path
from backend.schemas import IdeaInput,Session,AgentAnswer
from backend.services import parse_idea,generate_targets,build_card
from backend.context import PersonaAgent
from backend.orchestrator import Orchestrator
from backend.prompts import ROUNDS,PRE,POST
from backend.llm import LLMClient

class BudgetClient:
    def __init__(self,client,ceiling,calls):
        self.client=client; self.ceiling=ceiling; self.calls=calls; self.remaining=ceiling; self.used=0; self.allocations=[]
        self.per_call=ceiling//calls
        if self.per_call<128: raise ValueError('budget too small for all conditions; use >=3072')
    def call(self,task,payload,schema,max_tokens=700,seed=42,repair=True):
        if task!='agent': return self.client.call(task,payload,schema,max_tokens,seed,repair)
        cap=min(self.per_call,self.remaining)
        if cap<128: raise ValueError('completion budget exhausted')
        before=len(self.client.records)
        result=self.client.call(task,payload,schema,cap,seed,repair=False)
        record=self.client.records[before]
        used=record.get('completion_tokens')
        if self.client.mode=='qwen' and used is None: raise ValueError('real experiment requires server completion usage')
        # Mock reserves allocation; it cannot measure tokenizer/model usage.
        used=cap if used is None else used
        if used>cap: raise ValueError('server exceeded completion cap')
        self.remaining-=used; self.used+=used; self.allocations.append(cap)
        return result

def prepare(idea,llm):
    brief=parse_idea(idea); targets=generate_targets(brief,idea.evidence,llm); cards=[]
    # Experiment selection is predefined exposure/user/decision contrast, unlike product's human selection.
    for n,t in enumerate(targets[:3]): cards.append(build_card(t,cards,idea.evidence,llm,f'p{n+1}')[0])
    return brief,targets,cards

def condition(name,idea,brief,targets,cards,llm,ceiling=6000,seed=42):
    count=8 if name in ('A','B') else 24
    budget=BudgetClient(llm,ceiling,count); start=len(llm.records); stamp=time.perf_counter()
    questions=[('Private Pre',PRE)]+ROUNDS+[('Private Post',POST)]; responses=[]
    if name=='A':
        for rnd,q in questions:
            answer=budget.call('agent',{'brief':brief.model_dump(mode='json'),'question':q,'round':rnd,'instruction':'Generic business feedback; no persona role','history':responses[-8:]},AgentAnswer,seed=seed)
            responses.append({'round':rnd,**answer.model_dump(mode='json')})
    elif name in ('B','C'):
        for card in cards[:1] if name=='B' else cards:
            agent=PersonaAgent(card,budget)
            for n,(rnd,q) in enumerate(questions):
                answer=agent.answer(brief,'independent',rnd,q,max_tokens=budget.per_call,seed=seed,repair=False)
                row={'id':f'{card.id}-{n}','persona_id':card.id,'phase':'independent','round':rnd,**answer.model_dump(mode='json')}
                responses.append(row); agent.context.add(row)
    elif name=='D':
        s=Session(id='experiment',input=idea,brief=brief,targets=targets,cards=cards,mode=llm.mode)
        Orchestrator(budget).run(s,max_tokens=budget.per_call,seed=seed,repair=False)
        responses=[t.model_dump(mode='json') for t in s.transcript]
    else: raise ValueError('unknown condition')
    assert len(budget.allocations)==count and budget.used<=ceiling
    usage=llm.usage(start)
    generation=[r for r in usage['records'] if r['task']=='agent']
    return {'condition':name,'seed':seed,'model':llm.model,'mode':llm.mode,'completion_ceiling':ceiling,
            'completion_used_or_mock_reserved':budget.used,'mock_tokens_measured':False,'responses':responses,
            'latency_s':time.perf_counter()-stamp,'generation_usage':generation,'total_usage_including_report':usage,
            'metrics':None,'annotation_required':True}

def bootstrap_differences(rows,metric,seed=42,samples=2000,baseline='B'):
    paired={}
    for r in rows:
        value=r.get('metrics',{}).get(metric) if r.get('metrics') else None
        if value is not None: paired.setdefault(r['case_id'],{}).setdefault(r['condition'],[]).append(value)
    diffs=[statistics.mean(v['D'])-statistics.mean(v[baseline]) for v in paired.values() if 'D'in v and baseline in v]
    if len(diffs)<2: return {'pairs':len(diffs),'mean_difference':statistics.mean(diffs) if diffs else None,'ci95':None}
    rng=random.Random(seed); means=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(samples))
    return {'pairs':len(diffs),'mean_difference':statistics.mean(diffs),'ci95':[means[int(samples*.025)],means[int(samples*.975)]]}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--idea',default='examples/idea.json'); p.add_argument('--out',default='eval/runs/experiment.jsonl')
    p.add_argument('--mode',choices=['mock','qwen'],default='mock'); p.add_argument('--budget',type=int,default=6000); p.add_argument('--seeds',default='42,43,44')
    a=p.parse_args(); idea=IdeaInput.model_validate_json(Path(a.idea).read_text(encoding='utf-8')); llm=LLMClient(mode=a.mode)
    brief,targets,cards=prepare(idea,llm); rows=[]
    for seed in map(int,a.seeds.split(',')):
        order=list('ABCD'); random.Random(seed).shuffle(order)
        for name in order: rows.append({'case_id':Path(a.idea).stem,'dataset_kind':'synthetic',**condition(name,idea,brief,targets,cards,llm,a.budget,seed)})
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    print(json.dumps({'runs':len(rows),'output':a.out,'notice':'Unannotated generated candidates; no effectiveness result.'}))
