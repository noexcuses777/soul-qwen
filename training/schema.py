from typing import Literal
from pydantic import Field
from backend.schemas import Model,PersonaCard

class SFTExample(Model):
    source_id: str
    split: Literal['train','validation']
    synthetic: bool = True
    card: PersonaCard
    messages: list[dict]
    target: str
    behavior_tags: list[str] = Field(default_factory=list)

class PreferenceExample(Model):
    source_id: str
    split: Literal['train','validation']
    synthetic: bool = True
    card: PersonaCard
    prompt: str
    chosen: str
    rejected: str
    rationale: str
