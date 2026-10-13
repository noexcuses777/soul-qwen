from pydantic import BaseModel,ConfigDict,Field,model_validator

class ConfidenceObservation(BaseModel):
    probability: float = Field(ge=0,le=1)
    observed: int = Field(ge=0,le=1)

class Annotations(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_kind: str = 'human'
    predicted_themes: list[str] = Field(default_factory=list)
    real_themes: list[str] | None = None
    supported_ids: list[str] | None = None
    valid_ids: list[str] | None = None
    false_ids: list[str] | None = None
    novel_useful_ids: list[str] | None = None
    predicted_alternatives: list[str] = Field(default_factory=list)
    real_alternatives: list[str] | None = None
    predicted_barriers: list[str] = Field(default_factory=list)
    real_barriers: list[str] | None = None
    predicted_contradictions: list[str] = Field(default_factory=list)
    real_contradictions: list[str] | None = None
    consistent_turns: int | None = Field(default=None,ge=0)
    judged_turns: int | None = Field(default=None,ge=0)
    unjustified_majority_changes: int | None = Field(default=None,ge=0)
    change_opportunities: int | None = Field(default=None,ge=0)
    founder_usefulness: float | None = Field(default=None,ge=1,le=5)
    confidence_observations: list[ConfidenceObservation] = Field(default_factory=list)

    @model_validator(mode='after')
    def check(self):
        if self.dataset_kind not in ('human','synthetic'): raise ValueError('dataset_kind must be human or synthetic')
        for n,d in [(self.consistent_turns,self.judged_turns),(self.unjustified_majority_changes,self.change_opportunities)]:
            if n is not None and d is not None and n>d: raise ValueError('numerator exceeds denominator')
        p=set(self.predicted_themes)
        for ids in [self.supported_ids,self.valid_ids,self.false_ids,self.novel_useful_ids]:
            if ids is not None and not set(ids)<=p: raise ValueError('annotated insight IDs must be predicted IDs')
        if self.valid_ids is not None and self.false_ids is not None and set(self.valid_ids)&set(self.false_ids): raise ValueError('valid and false IDs overlap')
        return self

def recall(pred,real):
    if not real: return None
    return len(set(pred)&set(real))/len(set(real))

def ratio(n,d): return n/d if n is not None and d else None

def metrics(a:Annotations,usage=None,latency=None):
    p=set(a.predicted_themes); obs=a.confidence_observations
    brier=sum((o.probability-o.observed)**2 for o in obs)/len(obs) if obs else None
    ece=0 if obs else None
    for b in range(10):
        group=[o for o in obs if min(9,int(o.probability*10))==b]
        if group: ece+=len(group)/len(obs)*abs(sum(o.probability for o in group)/len(group)-sum(o.observed for o in group)/len(group))
    return {
      'dataset_kind':a.dataset_kind,'valid_insight_count':len(set(a.valid_ids)) if a.valid_ids is not None else None,
      'theme_recall':recall(p,a.real_themes),'novel_useful_insight':len(set(a.novel_useful_ids)) if a.novel_useful_ids is not None else None,
      'false_insight_rate':ratio(len(set(a.false_ids)) if a.false_ids is not None else None,len(p)),
      'unsupported_insight_rate':ratio(len(p-set(a.supported_ids)) if a.supported_ids is not None else None,len(p)),
      'divergence_detection':recall(a.predicted_contradictions,a.real_contradictions),
      'contradiction_discovery':recall(a.predicted_contradictions,a.real_contradictions),
      'alternative_recall':recall(a.predicted_alternatives,a.real_alternatives),'barrier_recall':recall(a.predicted_barriers,a.real_barriers),
      'persona_consistency':ratio(a.consistent_turns,a.judged_turns),'conformity_rate':ratio(a.unjustified_majority_changes,a.change_opportunities),
      'founder_usefulness':a.founder_usefulness,'confidence_brier':brier,'confidence_ece':ece,
      'cost':usage,'latency_s':latency,'notice':'Synthetic demo only' if a.dataset_kind=='synthetic' else 'Human-coded sample metrics; not population market validation'}
