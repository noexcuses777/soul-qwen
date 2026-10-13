"""Join independently coded annotations onto A-D outputs; do not infer human labels."""
import argparse,csv,json,statistics
from pathlib import Path
from .metrics import Annotations,metrics
from .experiment import bootstrap_differences

def analyze(runs,annotations,out,price=0):
    generated=[json.loads(l) for l in Path(runs).read_text(encoding='utf-8').splitlines() if l.strip()]
    labelled={}
    for line in Path(annotations).read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        row=json.loads(line);key=(row['case_id'],row['condition'],row['seed'])
        if key in labelled:raise ValueError('duplicate annotation key')
        labelled[key]=Annotations.model_validate(row['annotations'])
    rows=[]
    for r in generated:
        key=(r['case_id'],r['condition'],r['seed']);a=labelled.get(key)
        if a is None: continue
        usage=r['generation_usage']; measured=r['mode']=='qwen' and all('prompt_tokens'in x and 'completion_tokens'in x for x in usage)
        cost=sum(x['prompt_tokens']+x['completion_tokens'] for x in usage)*price/1_000_000 if measured else None
        rows.append({**r,'dataset_kind':a.dataset_kind,'metrics':metrics(a,cost,r['latency_s'])})
    if not rows:raise ValueError('no matching human/synthetic annotations; no effectiveness result can be computed')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    keys=[k for k in rows[0]['metrics'] if k not in ('notice','dataset_kind')]
    with (out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['case_id','condition','seed','dataset_kind']+keys)
        for r in rows:w.writerow([r['case_id'],r['condition'],r['seed'],r['dataset_kind']]+[r['metrics'][k] for k in keys])
    comparisons={baseline:{k:bootstrap_differences(rows,k,baseline=baseline) for k in keys} for baseline in 'ABC'}
    result={'annotated_runs':len(rows),'synthetic':any(r['dataset_kind']=='synthetic' for r in rows),
            'D_minus_baseline':comparisons,'notice':'Only human-coded sample comparisons support pilot assessment; synthetic or mock is smoke only.'}
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runs',required=True);p.add_argument('--annotations',required=True);p.add_argument('--out',default='eval/runs/analysis')
    p.add_argument('--price-per-million',type=float,default=0);a=p.parse_args()
    if a.price_per_million<0:raise ValueError('price cannot be negative')
    print(json.dumps(analyze(a.runs,a.annotations,a.out,a.price_per_million),ensure_ascii=False,indent=2))
