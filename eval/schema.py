from typing import Literal
from pydantic import Field,model_validator
from backend.schemas import Model,IdeaInput,PersonaCard,AgentAnswer
from .metrics import Annotations

AXES=['Evidence-grounded Persona Fidelity','Cross-turn Consistency','Epistemic Restraint','Problem Experience Specificity','Decision Realism','Need Articulation','Non-sycophancy','Grounded Disagreement','Multi-party Independence & Refinement']

class EvalCase(Model):
    case_id: str
    dataset_kind: Literal['synthetic','human']
    source_split: str
    source_ids: list[str] = Field(default_factory=list)
    idea: IdeaInput
    card: PersonaCard
    question: str
    history: list[dict] = Field(default_factory=list)
    gold_response: str | None = None
    gold_origin: Literal['none','human_annotated'] = 'none'
    human_annotations: Annotations | None = None
    @model_validator(mode='after')
    def check(self):
        if self.gold_response and self.gold_origin!='human_annotated': raise ValueError('Gold must identify human annotation origin')
        if self.dataset_kind=='synthetic' and self.gold_response: raise ValueError('synthetic demo cannot claim human Gold')
        if self.human_annotations and self.human_annotations.dataset_kind!=self.dataset_kind: raise ValueError('annotation dataset kind mismatch')
        return self

class CriterionScore(Model):
    score: int | None = Field(default=None,ge=1,le=5)
    rationale: str

class JudgeScores(Model):
    scores: dict[str,CriterionScore]
    @model_validator(mode='after')
    def check(self):
        if set(self.scores)!=set(AXES): raise ValueError('nine PSV axes required')
        return self

class PairChoice(Model):
    winner: Literal['A','B','tie']
    reason: str
