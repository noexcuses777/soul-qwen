from enum import IntEnum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

UNKNOWN = "UNKNOWN"
CATEGORIES = ['IT','교육','금융','운영관리','네트워킹','농업/축산업','라이프스타일','모빌리티','마케팅/PR','미디어/엔터테인먼트','바이오/의료','에너지/자원','유통/물류','임팩트','재무','프롭테크','하드웨어','기타','패션','F&B','뷰티','생활']

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_max_length=6000)

class EvidenceLevel(IntEnum):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4

class Evidence(Model):
    source_id: str = Field(min_length=1, max_length=80)
    text: str
    level: EvidenceLevel
    consent_note: str = UNKNOWN

class IdeaInput(Model):
    q1: str = Field(min_length=1,max_length=500)
    q2: str = ''
    q3: str = ''
    q3_1: str = ''
    q3_2: str = ''
    q4: str = ''
    q4_1: str = ''
    q5: str
    customer_type: Literal['개인 고객에게 팝니다','기업·기관에 팝니다','아직 모르겠어요'] = '아직 모르겠어요'
    founder_strength: str = ''
    evidence: list[Evidence] = Field(default_factory=list,max_length=8)

    @model_validator(mode='after')
    def check(self):
        if self.q5 not in CATEGORIES: raise ValueError('Q5 must be a listed category')
        if not self.q1.strip(): raise ValueError('Q1 cannot be blank')
        ids=[e.source_id for e in self.evidence]
        if len(ids)!=len(set(ids)): raise ValueError('duplicate source_id')
        return self

class IdeaBrief(Model):
    one_line: str
    background: str = UNKNOWN
    problem: str = UNKNOWN
    solution: str = UNKNOWN
    expected_user: str = UNKNOWN
    use_context: str = UNKNOWN
    current_alternatives: list[str] = Field(default_factory=list)
    value_proposition: str = UNKNOWN
    revenue_model: str = UNKNOWN
    pricing: str = UNKNOWN
    realization: str = UNKNOWN
    go_to_market: str = UNKNOWN
    business_category: str
    customer_type: str = UNKNOWN
    founder_strength: str = UNKNOWN
    uncertainties: list[str] = Field(default_factory=list)

class Target(Model):
    id: str = ''
    segment_name: str
    why_relevant: str
    problem_exposure: str = UNKNOWN
    expected_current_alternative: str = UNKNOWN
    buying_role: str = UNKNOWN
    critical_unknowns: list[str] = Field(default_factory=list)
    confidence: Literal['low','medium','high'] = 'low'
    evidence_level: EvidenceLevel = EvidenceLevel.L0
    evidence_ids: list[str] = Field(default_factory=list)
    relevance: float = Field(default=.5,ge=0,le=1)

class TargetBatch(Model):
    targets: list[Target] = Field(min_length=6,max_length=8)

class TargetReviewItem(Model):
    index: int = Field(ge=0,le=7)
    is_participant: bool
    fits_idea: bool
    reason: str = Field(max_length=120)

class TargetReview(Model):
    items: list[TargetReviewItem] = Field(min_length=1,max_length=8)

class TargetAudit(Model):
    stage: Literal['recommendation','selection','replaced']
    targets: list[Target]
    review: TargetReview | None = None
    issues: list[str] = Field(default_factory=list)

class Identity(Model):
    segment: str
    role: str = UNKNOWN
    use_context: str = UNKNOWN
    age: str = UNKNOWN
    gender: str = UNKNOWN
    income: str = UNKNOWN
    occupation: str = UNKNOWN
    life_stage: str = UNKNOWN
    region: str = UNKNOWN
    technical_literacy: str = UNKNOWN
    domain_experience: str = UNKNOWN

class ProblemContext(Model):
    current_alternative: str = UNKNOWN
    problem_severity: str = UNKNOWN
    frequency: str = UNKNOWN
    trigger: str = UNKNOWN
    workaround: str = UNKNOWN
    past_failed_attempts: list[str] = Field(default_factory=list)

class DecisionModel(Model):
    adoption_barrier: str = UNKNOWN
    buying_role: str = UNKNOWN
    switching_cost: str = UNKNOWN
    budget_constraint: str = UNKNOWN
    decision_criteria: list[str] = Field(default_factory=list)
    risk_sensitivity: str = UNKNOWN
    decision_authority: str = UNKNOWN
    must_have: list[str] = Field(default_factory=list)
    rejection_conditions: list[str] = Field(default_factory=list)

class Goals(Model):
    desired_outcome: str = UNKNOWN
    priority: str = UNKNOWN
    risk_tolerance: str = UNKNOWN
    functional_goal: str = UNKNOWN
    emotional_goal: str = UNKNOWN
    social_goal: str = UNKNOWN
    motivation: str = UNKNOWN

class Anchor(Model):
    source_id: str
    field: str
    quote: str
    level: EvidenceLevel

class Style(Model):
    speech: str = '간결하고 자연스러운 한국어'
    directness: str = '조건과 이유를 먼저 설명'
    verbosity: str = '짧은 2–3문장'
    emotional_expression: str = UNKNOWN
    technical_vocabulary: str = UNKNOWN
    question_style: str = UNKNOWN
    agreement_threshold: str = '자신의 조건과 근거가 맞을 때만 조건부 동의'
    uncertainty_expression: str = '모르는 조건을 구분해 설명'

class StableProfile(Model):
    core_values: list[str] = Field(default_factory=list)
    stable_constraints: list[str] = Field(default_factory=list)
    stable_preferences: list[str] = Field(default_factory=list)
    key_history: list[str] = Field(default_factory=list)

class ReasoningRule(Model):
    id: str = Field(min_length=1,max_length=24)
    trigger: str = Field(min_length=1,max_length=100)
    value: str = Field(min_length=1,max_length=80)
    tradeoff: str = Field(min_length=1,max_length=100)
    conditional_choice: str = Field(min_length=1,max_length=120)
    basis_fields: list[str] = Field(min_length=1,max_length=3)
    evidence_ids: list[str] = Field(default_factory=list,max_length=3)
    unknowns: list[str] = Field(default_factory=list,max_length=3)
    kind: Literal['hypothesis'] = 'hypothesis'

class TimelineEvent(Model):
    source_id: str
    event_quote: str = Field(min_length=1,max_length=500)
    when: str = Field(default=UNKNOWN,max_length=80)

class Presentation(Model):
    display_name: str = Field(default='',max_length=24)
    fictional: Literal[True] = True

class NameEdit(Model):
    display_name: str = Field(min_length=1,max_length=24)
    @model_validator(mode='after')
    def check(self):
        self.display_name=self.display_name.strip()
        if not self.display_name or any(ord(c)<32 for c in self.display_name): raise ValueError('Use a nonempty single-line name')
        return self

class Core(Model):
    model_config = ConfigDict(extra='forbid',frozen=True)
    identity_context: Identity
    problem_context: ProblemContext = Field(default_factory=ProblemContext)
    decision_model: DecisionModel = Field(default_factory=DecisionModel)
    goals_motivations: Goals = Field(default_factory=Goals)
    evidence_anchors: list[Anchor] = Field(default_factory=list)
    interaction_style: Style = Field(default_factory=Style)
    stable_profile: StableProfile = Field(default_factory=StableProfile)
    reasoning_rules: list[ReasoningRule] = Field(default_factory=list,max_length=2)
    timeline: list[TimelineEvent] = Field(default_factory=list,max_length=4)
    hypothesis: Literal[True] = True

class SessionState(Model):
    model_config = ConfigDict(extra='forbid',str_max_length=600)
    stance: Literal['unknown','conditional','positive','negative'] = 'unknown'
    reasons: list[str] = Field(default_factory=list,max_length=8)
    unresolved_issues: list[str] = Field(default_factory=list,max_length=8)
    revisions: list[str] = Field(default_factory=list,max_length=8)

class PersonaCard(Model):
    id: str
    immutable_core: Core
    session_state: SessionState = Field(default_factory=SessionState)
    presentation: Presentation = Field(default_factory=Presentation)

class ValidationIssue(Model):
    kind: Literal['contradiction','unsupported_detail','stereotype','similarity','forced_pro_con','unknown_handling']
    detail: str

class ValidationResult(Model):
    issues: list[ValidationIssue] = Field(default_factory=list)
    advisory: list[ValidationIssue] = Field(default_factory=list)
    @property
    def valid(self): return not self.issues

class Selection(Model):
    target_ids: list[str] = Field(default_factory=list,max_length=3)
    custom_targets: list[Target] = Field(default_factory=list,max_length=3)
    display_names: dict[str,str] = Field(default_factory=dict,max_length=3)
    @model_validator(mode='after')
    def check(self):
        if not 1 <= len(self.target_ids)+len(self.custom_targets) <= 3: raise ValueError('select/add 1-3 targets')
        if len(set(self.target_ids))!=len(self.target_ids): raise ValueError('duplicate selected target')
        chosen=self.target_ids+[t.id for t in self.custom_targets]
        if self.display_names:
            if set(self.display_names)!=set(chosen): raise ValueError('Display names must match all selected targets')
            self.display_names={key:NameEdit(display_name=value).display_name for key,value in self.display_names.items()}
            if len(set(self.display_names.values()))!=len(chosen): raise ValueError('Use different display names')
        return self

class AgentAnswer(Model):
    content: str = Field(min_length=1,max_length=1400)
    stance: Literal['unknown','conditional','positive','negative'] = 'unknown'
    reason: str = Field(default=UNKNOWN,max_length=400)
    unresolved_issues: list[str] = Field(default_factory=list,max_length=8)
    evidence_ids: list[str] = Field(default_factory=list,max_length=8)
    reply_to: str | None = None
    reasoning_rule_ids: list[str] = Field(default_factory=list,max_length=2)
    quality_flags: list[str] = Field(default_factory=list,max_length=4)
    generated_content: str | None = Field(default=None,max_length=1400)

class OwnBasis(Model):
    role: str
    expected_alternative: str

class InteractionAnswer(AgentAnswer):
    dialogue_act: Literal['answer','question','clarify','disagree','agree','close'] = 'answer'
    addressed_to: str | None = None
    followup_question: str = Field(default='',max_length=140)
    followup_kind: Literal['none','peer_condition','clarification','real_world_check'] = 'none'
    own_basis: OwnBasis | None = None
    @classmethod
    def model_json_schema(cls,*args,**kwargs):
        raw=super().model_json_schema(*args,**kwargs)
        if cls is InteractionAnswer:
            raw['required']=list(dict.fromkeys(raw.get('required',[])+['dialogue_act','addressed_to','followup_question']))
            raw['properties']['content']['maxLength']=900
        return raw

class Utterance(InteractionAnswer):
    id: str
    persona_id: str
    phase: Literal['pre','group','post','independent','generic']
    round: str
    question: str
    selection_reason: str = ''
    speaker_scores: dict[str,float] = Field(default_factory=dict)
    directed_to: str | None = None
    thread_id: str | None = None
    snapshot_revision: int | None = None

class QuestionSuggestion(Model):
    id: str = ''
    question: str = Field(min_length=1,max_length=140)
    topic: Literal['Problem Reality','Solution Reaction','Cross-reaction','Conflict Probe','Adoption/Payment Reality','Failure Condition']
    why: str = Field(min_length=1,max_length=100)
    persona_id: str | None = None

class QuestionPlan(Model):
    suggestions: list[QuestionSuggestion] = Field(min_length=6,max_length=6)
    @model_validator(mode='before')
    @classmethod
    def decode_topics(cls,raw):
        if isinstance(raw,dict) and isinstance(raw.get('suggestions'),dict):
            raw={**raw,'suggestions':[{**row,'topic':topic} for topic,row in raw['suggestions'].items()]}
        return raw
    @classmethod
    def model_json_schema(cls,*args,**kwargs):
        raw=super().model_json_schema(*args,**kwargs)
        suggestion=raw['$defs']['QuestionSuggestion']
        suggestion['properties'].pop('topic'); suggestion['properties'].pop('id')
        suggestion['required']=[k for k in suggestion['required'] if k!='topic']
        topics=['Problem Reality','Solution Reaction','Cross-reaction','Conflict Probe','Adoption/Payment Reality','Failure Condition']
        raw['properties']['suggestions']={'type':'object','properties':{name:{'$ref':'#/$defs/QuestionSuggestion'} for name in topics},
                                        'required':topics,'additionalProperties':False}
        return raw

class LoungeStart(Model):
    mode: Literal['guided','moderated'] = 'guided'

class ConversationThread(Model):
    id: str
    question: str
    utterance_ids: list[str] = Field(default_factory=list)
    status: Literal['active','returned_to_user','closed'] = 'active'
    stop_reason: str = ''
    remaining_issues: list[str] = Field(default_factory=list,max_length=8)

class LoungeQuestion(Model):
    question: str = Field(min_length=1,max_length=500)
    persona_id: str | None = None
    interaction: Literal['auto','direct','interactive'] = 'auto'

class NextQuestionRequest(Model):
    revision: int | None = Field(default=None,ge=0)

class FollowupCandidate(Model):
    question: str = Field(min_length=8,max_length=500)
    why: str = Field(min_length=1,max_length=220)
    issue: str = Field(min_length=1,max_length=100)
    angle: str = Field(min_length=1,max_length=100)
    new_condition: str = Field(min_length=1,max_length=180)
    source_utterance_ids: list[str] = Field(min_length=1,max_length=3)

class FollowupPlan(Model):
    candidates: list[FollowupCandidate] = Field(max_length=3)
    missing_information: list[str] = Field(max_length=4)
    evidence_question: str = Field(max_length=500)
    why: str = Field(min_length=1,max_length=220)

class FollowupJudgment(Model):
    index: int = Field(ge=0,le=2)
    novel: bool
    answerable: bool
    why: str = Field(min_length=1,max_length=220)

class FollowupReview(Model):
    reviews: list[FollowupJudgment] = Field(max_length=3)

class FollowupRecommendation(Model):
    id: str
    revision: int = Field(ge=0)
    status: Literal['discussion','needs_evidence','no_new_question']
    question: str = Field(default='',max_length=500)
    why: str = Field(min_length=1,max_length=220)
    source_utterance_ids: list[str] = Field(default_factory=list,max_length=3)
    missing_information: list[str] = Field(default_factory=list,max_length=4)

SECTIONS = ['Target Snapshot','Problem Signal','Solution Reaction','Target Differences','Agreement','Disagreement','Unknown/Unsupported','Real Interview Next Steps']

class Insight(Model):
    text: str
    utterance_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    hypothesis: Literal[True] = True
    confidence: Literal['low','medium','high'] = 'low'
    evidence_level: EvidenceLevel = EvidenceLevel.L0

class Report(Model):
    sections: dict[str,list[Insight]]
    notice: str = 'AI 시뮬레이션 가설입니다. 실제 시장 검증이나 구매 확정이 아닙니다.'
    @classmethod
    def model_json_schema(cls,*args,**kwargs):
        raw=super().model_json_schema(*args,**kwargs)
        item={**raw['properties']['sections']['additionalProperties'],'minItems':1,'maxItems':1}
        # Bound report output as well as input; avoid a small model writing an unbounded essay.
        raw['$defs']['Insight']['properties']['text']['maxLength']=180
        raw['properties']['sections']={'type':'object','properties':{name:item for name in SECTIONS},
                                       'required':SECTIONS,'additionalProperties':False}
        return raw
    @model_validator(mode='after')
    def check(self):
        if set(self.sections)!=set(SECTIONS): raise ValueError('all eight report sections required')
        return self

class Session(Model):
    id: str
    input: IdeaInput
    brief: IdeaBrief
    targets: list[Target]
    # Cosmetic aliases are separate from the target schema used by the model.
    target_display_names: dict[str,str] = Field(default_factory=dict)
    target_audits: list[TargetAudit] = Field(default_factory=list)
    cards: list[PersonaCard] = Field(default_factory=list)
    # Presentation association only; never included in the model's persona core.
    selected_target_ids: list[str] = Field(default_factory=list,max_length=3)
    validations: list[ValidationResult] = Field(default_factory=list)
    transcript: list[Utterance] = Field(default_factory=list)
    states: dict[str,SessionState] = Field(default_factory=dict)
    report: Report | None = None
    report_revision: int | None = None
    report_generated_at: str | None = None
    report_stale: bool = False
    status: str = 'CREATED'
    state_history: list[str] = Field(default_factory=lambda:['CREATED'])
    mode: Literal['mock','qwen']
    usage: dict = Field(default_factory=dict)
    error: str | None = None
    calibration: dict | None = None
    calibration_revision: int | None = None
    pending_question: str | None = None
    pending_speaker: str | None = None
    protocol_version: str = '2'
    dialogue_runtime: dict = Field(default_factory=dict)
    chat_events: list[dict] = Field(default_factory=list)
    suggestions: list[QuestionSuggestion] = Field(default_factory=list)
    threads: list[ConversationThread] = Field(default_factory=list)
    lounge_mode: Literal['guided','moderated'] | None = None
