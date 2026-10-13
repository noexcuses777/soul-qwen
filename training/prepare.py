import argparse,json
from pathlib import Path
from .schema import SFTExample,PreferenceExample

def prepare(source,out,kind,eval_file):
    held=set()
    for line in Path(eval_file).read_text(encoding='utf-8').splitlines():
        if line.strip(): held.update(json.loads(line).get('source_ids',[]))
    schema=SFTExample if kind=='sft' else PreferenceExample; rows=[]; train=set(); valid=set()
    for line in Path(source).read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        r=schema.model_validate_json(line)
        if r.source_id in held: raise ValueError('evaluation leakage: '+r.source_id)
        (train if r.split=='train' else valid).add(r.source_id)
        system='Follow immutable PersonaCard; no fabricated experiences, flattery or purchase commitments.\n'+r.card.model_dump_json()
        if kind=='sft': row={'messages':[{'role':'system','content':system}]+r.messages+[{'role':'assistant','content':r.target}]}
        else: row={'prompt':[{'role':'system','content':system},{'role':'user','content':r.prompt}],
                   'chosen':[{'role':'assistant','content':r.chosen}],'rejected':[{'role':'assistant','content':r.rejected}]}
        row.update({'source_id':r.source_id,'split':r.split,'synthetic':r.synthetic}); rows.append(row)
    if train&valid: raise ValueError('source leakage between train and validation')
    Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    return len(rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['sft','preference'],required=True);p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--eval',default='eval/data/synthetic_demo.jsonl');a=p.parse_args()
    print('Prepared',prepare(a.source,a.out,a.kind,a.eval),'rows; no fine-tuning performed.')
