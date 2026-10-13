"""Human-coded atomic claim diagnostics; NOT a replication of ACC_atom/IC_atom/RC_atom."""
import argparse,json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

class Atom(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str
    turn_id:str
    persona_id:str
    text:str
    kind:Literal['fact','hypothesis','unknown']
    supported:bool | None=None
    source_ids:list[str]=Field(default_factory=list)
    basis_fields:list[str]=Field(default_factory=list)
    contradicts_atom_ids:list[str]=Field(default_factory=list)
    annotation_reason:str

class AtomicAnnotations(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_kind:Literal['human','synthetic']
    annotator:str
    atoms:list[Atom]
    @model_validator(mode='after')
    def check(self):
        ids=[a.id for a in self.atoms]
        if len(set(ids))!=len(ids):raise ValueError('duplicate atom ID')
        seen=set()
        for atom in self.atoms:
            if not set(atom.contradicts_atom_ids)<=seen:raise ValueError('contradictions must reference earlier annotated atoms')
            seen.add(atom.id)
        return self

def metrics(a):
    facts=[x for x in a.atoms if x.kind=='fact' and x.supported is not None]
    interpreted=[x for x in a.atoms if x.kind=='hypothesis' and x.supported is not None]
    ratio=lambda xs:sum(x.supported for x in xs)/len(xs) if xs else None
    return {'dataset_kind':a.dataset_kind,'annotated_atom_count':len(a.atoms),'judged_fact_count':len(facts),
        'grounded_fact_rate':ratio(facts),'grounded_hypothesis_rate':ratio(interpreted),
        'contradictory_atom_count':sum(bool(x.contradicts_atom_ids) for x in a.atoms),
        'notice':'Human labels required; synthetic numbers do not establish fidelity. Adapted diagnostics, not published ACC_atom/IC_atom/RC_atom.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('annotations');p.add_argument('--out',required=True);a=p.parse_args()
    data=AtomicAnnotations.model_validate_json(Path(a.annotations).read_text(encoding='utf-8'))
    Path(a.out).write_text(json.dumps(metrics(data),ensure_ascii=False,indent=2),encoding='utf-8')
