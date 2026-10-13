import json,re,uuid
from .schemas import *
from .limits import check_target
from .quantities import quantity_texts, unsupported_quantities
from .display_names import ensure_names, random_name

def brief_payload(brief):
    data=brief.model_dump(mode='json')
    # Keep canonical founder wording once, without repeating it under three semantic fields.
    if data['solution']==data['problem']: data.pop('solution')
    if data['value_proposition']==data['problem']: data.pop('value_proposition')
    if data['go_to_market']==data['realization']: data.pop('go_to_market')
    return data

def evidence_windows(evidence,query,anchors=()):
    """Local lexical retrieval only. ID, original offset and level survive every excerpt."""
    words=set(re.findall(r'\w{2,}',query.lower()))
    rows=[]
    for e in evidence:
        chunks=[(i,e.text[i:i+450]) for i in range(0,len(e.text),450)] or [(0,'')]
        ranked=sorted(chunks,key=lambda x:(-sum(w in x[1].lower() for w in words),x[0]))[:2]
        spans=sorted(ranked)
        row={'source_id':e.source_id,'level':int(e.level),
             'excerpts':[{'offset':offset,'text':text} for offset,text in spans],
             'excerpt_only':len(chunks)>2}
        quotes=[a.quote for a in anchors if a.source_id==e.source_id and a.quote in e.text]
        if quotes: row['anchored_quotes']=quotes
        rows.append(row)
    return rows

def specific_paths(core):
    allowed={'identity_context.segment','identity_context.role','identity_context.use_context',
             'problem_context.current_alternative','decision_model.buying_role'}
    for owner in ('identity_context','problem_context','decision_model','goals_motivations','stable_profile'):
        for key in type(getattr(core,owner)).model_fields:
            if f'{owner}.{key}' not in allowed: yield f'{owner}.{key}'

def parse_idea(i:IdeaInput)->IdeaBrief:
    def known(v): return v.strip() or UNKNOWN
    # Preserve each founder statement in its own semantic field. Legacy records without q3
    # still use q3_1 as the only available description; no missing audience is invented.
    return IdeaBrief(one_line=i.q1.strip(),background=known(i.q2),problem=known(i.q3_1),solution=known(i.q3 or i.q3_1),
                     value_proposition=known(i.q3_1),revenue_model=known(i.q3_2),realization=known(i.q4_1 or i.q4),
                     go_to_market=known(i.q4_1),business_category=i.q5,
                     customer_type=UNKNOWN if i.customer_type=='아직 모르겠어요' else i.customer_type,
                     founder_strength=known(i.founder_strength),
                     uncertainties=['expected_user','use_context','current_alternatives','pricing'])

def contrast_signature(t):
    return (t.problem_exposure,t.expected_current_alternative,t.buying_role)

def contrast_distance(a,b):
    scores=[]
    for x,y in zip(contrast_signature(a),contrast_signature(b)):
        tx,ty=set(x.split()),set(y.split())
        scores.append(1-len(tx&ty)/max(1,len(tx|ty)))
    return sum(scores)/len(scores)

def rank_contrasting(targets):
    pool=list(targets); ranked=[]
    while pool:
        candidate=max(pool,key=lambda t:.65*t.relevance+.35*(min(contrast_distance(t,r) for r in ranked) if ranked else 0))
        ranked.append(candidate);pool.remove(candidate)
    for n,t in enumerate(ranked):t.id=f't{n+1}'
    return ranked

def target_label_issue(target):
    """Reject unmistakable bare topics, without imposing a domain-specific customer allowlist."""
    name=target.segment_name.strip()
    if not name or name==UNKNOWN: return '어떤 사람·기관인지 명시되지 않았습니다.'
    if re.search(r'(?:검증|시나리오|가격\s*모델|지표|절감\s*효과|전환\s*경로|민감도|지불\s*의사|기대\s*효과)$',name):
        return '이용자 유형 대신 검증 과제·주제·가격·지표가 적혀 있습니다.'
    return None

def review_targets(brief,targets,llm):
    review=llm.call('target_review',{'brief':brief_payload(brief),
        'targets':[{'index':i,**t.model_dump(mode='json',exclude={'id'})} for i,t in enumerate(targets)]},
        TargetReview,max_tokens=650)
    indices=[x.index for x in review.items]
    if len(indices)!=len(targets) or set(indices)!=set(range(len(targets))):
        return review,['추천 검사에서 모든 이용자 후보를 확인하지 못했습니다.']
    issues=[]
    for item in review.items:
        t=targets[item.index]; local=target_label_issue(t)
        if local or not item.is_participant or not item.fits_idea:
            issues.append(f'{item.index+1}. {t.segment_name}: {local or item.reason}')
    return review,issues

def checked_target_sources(batch,evidence):
    known={e.source_id:e for e in evidence}; seen=set(); targets=[]
    for t in sorted(batch.targets,key=lambda t:-t.relevance):
        check_target(t)
        if not set(t.evidence_ids)<=set(known): raise ValueError('target invented evidence')
        if not t.evidence_ids: t.evidence_level=EvidenceLevel.L0; t.confidence='low'
        elif t.evidence_level>min(known[x].level for x in t.evidence_ids): raise ValueError('target level exceeds cited evidence')
        sig=contrast_signature(t)
        if sig in seen: continue
        seen.add(sig); t.id=f't{len(targets)+1}'; targets.append(t)
    return targets

def generate_targets(brief,evidence,llm,audits=None):
    payload={'brief':brief_payload(brief),'evidence':evidence_windows(evidence,brief.one_line+' '+brief.problem)}
    for attempt in range(2):
        batch=llm.call('targets',payload,TargetBatch,max_tokens=2100)
        targets=checked_target_sources(batch,evidence)
        review,issues=review_targets(brief,batch.targets,llm)
        if len(targets)<3: issues.append('문제 상황·현재 대안·도입 조건이 다른 이용자 후보가 최소 3개 필요합니다.')
        if audits is not None: audits.append(TargetAudit(stage='recommendation',targets=batch.targets,review=review,issues=issues))
        if not issues: return rank_contrasting(targets)
        payload['repair_feedback']=issues
    raise ValueError('이용자 유형에 맞는 타깃 추천을 완성하지 못했습니다. 아이디어를 유지한 채 다시 추천받아 주세요. '+ '; '.join(issues))

def target_signature(target):
    return target.model_dump(mode='json',exclude={'id'})

def validate_target_selection(brief,chosen,audits,llm):
    for t in chosen:
        check_target(t)
        issue=target_label_issue(t)
        if issue: raise ValueError(f'“{t.segment_name}”: {issue} 어떤 이용자인지 수정하거나 타깃을 다시 추천받아 주세요.')
    if len({t.segment_name.strip() for t in chosen})!=len(chosen):
        raise ValueError('같은 이용자 유형을 중복 선택했습니다. 서로 다른 타깃을 선택하세요.')
    approved=[target_signature(t) for a in audits if a.review is not None and not a.issues for t in a.targets]
    unreviewed=[t for t in chosen if target_signature(t) not in approved]
    if unreviewed:
        review,issues=review_targets(brief,unreviewed,llm)
        audit=TargetAudit(stage='selection',targets=unreviewed,review=review,issues=issues)
        if issues: raise ValueError('어떤 이용자인지 확인할 수 없습니다. 타깃 내용을 수정해 주세요. '+ '; '.join(issues))
        return audit

def get_field(core,path):
    obj=core.model_dump()
    for k in path.split('.'): obj=obj[k]
    return obj

def rule_issues(core,evidence):
    sources={e.source_id:e for e in evidence}; issues=[]; seen=set()
    for r in core.reasoning_rules:
        if r.id in seen: issues.append('duplicate reasoning rule ID')
        seen.add(r.id)
        for path in r.basis_fields:
            try: value=get_field(core,path)
            except (KeyError,TypeError): value=UNKNOWN
            if path.startswith(('reasoning_rules','timeline','interaction_style')) or value in (UNKNOWN,[],None):
                issues.append(f'{r.id}: missing factual/target basis {path}')
        if not set(r.evidence_ids)<=set(sources): issues.append(f'{r.id}: invented source')
    for t in core.timeline:
        source=sources.get(t.source_id)
        if not source or source.level<2 or t.event_quote not in source.text or (t.when!=UNKNOWN and t.when not in t.event_quote):
            issues.append('timeline event requires an original customer/interview/behavioral quote and supported date')
    return issues

def normalize_card(card,target,evidence):
    """Apply a deterministic evidence gate before semantic validation."""
    core=card.immutable_core; sources={e.source_id:e for e in evidence}
    valid=[]; anchored=set()
    for anchor in core.evidence_anchors:
        source=sources.get(anchor.source_id)
        if not source or not anchor.quote or anchor.quote not in source.text or anchor.level!=source.level:
            continue
        try: value=get_field(core,anchor.field)
        except (KeyError,TypeError): continue
        supported=(isinstance(value,str) and value!=UNKNOWN and value in anchor.quote) or \
                  (isinstance(value,list) and all(item in anchor.quote for item in value))
        if supported: valid.append(anchor); anchored.add(anchor.field)
    core.evidence_anchors[:]=valid

    # These fields are L0 target hypotheses. Preserve exact target wording.
    core.identity_context.segment=target.segment_name
    core.identity_context.role=target.buying_role
    core.identity_context.use_context=target.problem_exposure
    core.problem_context.current_alternative=target.expected_current_alternative
    core.decision_model.buying_role=target.buying_role
    for path in specific_paths(core):
        if path in anchored: continue
        owner,field=path.split('.')
        previous=getattr(getattr(core,owner),field)
        setattr(getattr(core,owner),field,[] if isinstance(previous,list) else UNKNOWN)
    if 'decision_model.decision_criteria' not in anchored:
        core.decision_model.decision_criteria=[]
    card.session_state.stance='unknown'
    if not card.session_state.unresolved_issues:
        card.session_state.unresolved_issues=target.critical_unknowns[:8]
    # Never silently turn unsupported history into an observed event.
    sources={e.source_id:e for e in evidence}
    core.timeline[:]=[t for t in core.timeline if t.source_id in sources and sources[t.source_id].level>=2
                      and t.event_quote in sources[t.source_id].text and (t.when==UNKNOWN or t.when in t.event_quote)]
    for rule in core.reasoning_rules:
        # A small model sometimes outputs schema labels instead of human-readable missing conditions.
        rule.unknowns=[u for u in rule.unknowns if u!='critical_unknowns' and not re.fullmatch(r'[a-z_]+\.[a-z_]+',u)]
        if not rule.unknowns: rule.unknowns=target.critical_unknowns[:3]
    return card

def validate_card(card,target,peers,evidence,llm):
    issues=[]; sources={e.source_id:e for e in evidence}; c=card.immutable_core
    def issue(kind,detail): issues.append(ValidationIssue(kind=kind,detail=detail))
    for detail in rule_issues(c,evidence): issue('unsupported_detail',detail)
    if c.identity_context.segment!=target.segment_name: issue('contradiction','segment does not match selected target')
    anchored=set()
    for a in c.evidence_anchors:
        if a.source_id not in sources or not a.quote or a.quote not in sources[a.source_id].text or a.level!=sources[a.source_id].level:
            issue('unsupported_detail','invalid anchor quote/level/source'); continue
        try: value=get_field(c,a.field)
        except (KeyError,TypeError): issue('unsupported_detail','anchor field not found'); continue
        # Conservative extractive gate; inferred detail must remain UNKNOWN in this MVP.
        if isinstance(value,str) and value!=UNKNOWN and value not in a.quote:
            issue('unsupported_detail',f'{a.field} is not supported verbatim by anchor'); continue
        if isinstance(value,list) and any(v not in a.quote for v in value):
            issue('unsupported_detail',f'{a.field} list contains unsupported items'); continue
        anchored.add(a.field)
    for f in specific_paths(c):
        if get_field(c,f) not in (UNKNOWN,[]) and f not in anchored: issue('unsupported_detail',f+' needs grounding or UNKNOWN')
    permitted={'identity_context.role':target.buying_role,'identity_context.use_context':target.problem_exposure,
               'problem_context.current_alternative':target.expected_current_alternative,'decision_model.buying_role':target.buying_role}
    for f,v in permitted.items():
        if get_field(c,f) not in (UNKNOWN,v) and f not in anchored: issue('unsupported_detail',f+' outside target and evidence')
    if c.decision_model.decision_criteria and 'decision_model.decision_criteria' not in anchored: issue('unsupported_detail','decision criteria need grounding')
    if card.session_state.stance!='unknown': issue('forced_pro_con','initial stance must be unknown')
    for peer in peers:
        p=peer.immutable_core
        if (p.identity_context.use_context,p.problem_context.current_alternative,p.decision_model.buying_role)==(c.identity_context.use_context,c.problem_context.current_alternative,c.decision_model.buying_role):
            issue('similarity','peer has identical exposure/alternative/decision profile')
    audit=llm.call('validate',{'card':card.model_dump(mode='json'),'target':target.model_dump(mode='json'),
         'peers':[{'id':p.id,'identity':p.immutable_core.identity_context.model_dump(),'problem':p.immutable_core.problem_context.model_dump(),'decision':p.immutable_core.decision_model.model_dump()} for p in peers],
         'evidence':evidence_windows(evidence,target.segment_name+' '+target.problem_exposure,c.evidence_anchors)},ValidationResult,max_tokens=450)
    # Objective evidence/UNKNOWN/similarity/stance rules above are authoritative and traceable.
    # The independent LLM audit blocks semantic contradiction and stereotype; its subjective
    # findings remain visible for human review without forcing endless sparse-card regeneration.
    blocking=[item for item in audit.issues if item.kind in ('contradiction','stereotype')]
    advisory=audit.advisory+[item for item in audit.issues if item.kind not in ('contradiction','stereotype')]
    return ValidationResult(issues=issues+blocking,advisory=advisory)

def build_card(target,peers,evidence,llm,persona_id,brief=None):
    feedback=[]
    for attempt in range(3):
        card=llm.call('build',{'target':target.model_dump(mode='json'),'persona_id':persona_id,
              'brief':brief_payload(brief) if brief else {},
              'evidence':evidence_windows(evidence,target.segment_name+' '+target.problem_exposure),'repair_feedback':feedback},PersonaCard,max_tokens=1100)
        card.id=persona_id
        card=normalize_card(card,target,evidence)
        audit=validate_card(card,target,peers,evidence,llm)
        if audit.valid:
            # Generated names are presentation metadata, independent of target traits.
            card.presentation.display_name=random_name({p.presentation.display_name for p in peers})
            return card,audit
        feedback=[i.model_dump() for i in audit.issues]
    raise ValueError('Persona failed validation after 3 builds: '+json.dumps(feedback,ensure_ascii=False))

def guard_report_consensus(session,report):
    """Withhold universal agreement whose citations do not cover the selected people.

    Coverage is necessary, not sufficient: this is not a semantic consensus judge.
    Retain the original generated claim in the session audit without an extra LLM call.
    """
    people={c.id for c in session.cards}
    turns={t.id:t for t in session.transcript}
    universal=re.compile(r'(?:모든\s*(?:참여자|페르소나|사람)|참여자\s*전원|세\s*(?:페르소나|참여자)\s*모두|전원.{0,12}(?:동의|합의)|all\s+(?:participants|personas)|everyone)',re.I)
    for row in report.sections.get('Agreement',[]):
        if not universal.search(row.text): continue
        cited={turns[uid].persona_id for uid in row.utterance_ids if uid in turns}
        if people<=cited: continue
        session.dialogue_runtime.setdefault('report_claim_audits',[]).append({
            'issue':'universal_agreement_missing_persona_citations',
            'public_revision':sum(t.phase=='group' for t in session.transcript),
            'original_claim':row.model_dump(mode='json'),
            'missing_persona_ids':sorted(people-cited),
            'semantic_consensus_verified':False})
        row.text='전체 참여자의 합의를 확인할 인용 근거가 부족합니다. 인용된 의견은 개별 가설로 확인하세요.'
        row.confidence='low'
        report.notice+=' 전체 합의의 인용 범위가 부족한 문장을 보류했습니다. 원문은 JSON 감사 기록에 보존됩니다.'
    return report

def report_quantity_basis(session,utterance_ids=(),revision=None):
    """Only founder text, human questions, own cited cards and cited real data.

    AI utterances, their reasons and another persona's generated view are not
    quantity evidence. The caller supplies a snapshot revision when projecting.
    """
    public=[t for t in session.transcript if t.phase=='group']
    revision=session.report_revision if revision is None else revision
    if revision is not None: public=public[:revision]
    visible_ids={t.id for t in public}
    owners={t.persona_id for t in session.transcript if t.id in utterance_ids}
    evidence_ids={sid for t in session.transcript if t.id in utterance_ids for sid in t.evidence_ids}
    founder={k:v for k,v in session.input.model_dump(mode='json').items() if k!='evidence'}
    questions=[thread.question for thread in session.threads if visible_ids.intersection(thread.utterance_ids)]
    return quantity_texts(founder,session.brief,questions,
        [card.immutable_core for card in session.cards if card.id in owners],
        [e.text for e in session.input.evidence if e.source_id in evidence_ids])


def guard_report_quantities(session,report,revision=None):
    """Classify unsupported numeric interview prompts without inventing a replacement.

    Mutates the supplied report/audit. Use detached copies for existing saved
    reports; generation calls this before saving a new report.
    """
    kept=[]; moved=False
    for row in report.sections['Real Interview Next Steps']:
        basis=report_quantity_basis(session,row.utterance_ids,revision)
        # Explicit source citations can supply real-data numbers as well.
        basis+=quantity_texts([e.text for e in session.input.evidence if e.source_id in row.evidence_ids])
        missing=unsupported_quantities(row.text,basis)
        if not missing:
            kept.append(row); continue
        session.dialogue_runtime.setdefault('report_claim_audits',[]).append({
            'issue':'unsupported_interview_quantity','original_claim':row.model_dump(mode='json'),
            'unsupported_quantities':missing,'public_revision':revision if revision is not None else session.report_revision})
        unknown=row.model_copy(deep=True)
        unknown.text='근거가 확인되지 않은 수치 조건이 포함된 생성 가설: '+row.text
        unknown.confidence='low'
        report.sections['Unknown/Unsupported'].append(unknown)
        moved=True
    report.sections['Real Interview Next Steps']=kept
    if moved:
        report.notice+=' 실제 인터뷰 질문에 근거 없는 수치 조건이 있어 미확인 항목으로 옮겼습니다. 수치 조건의 근거를 확인한 뒤 질문을 다시 구성하세요.'
    return report


def generate_report(session,llm):
    # Bounded excerpts preserve original IDs; all full text remains in stored transcript.
    private=[]
    for card in session.cards:
        pre=next((t for t in session.transcript if t.phase=='pre' and t.persona_id==card.id),None)
        post=next((t for t in reversed(session.transcript) if t.phase=='post' and t.persona_id==card.id),None)
        private.extend(t for t in (pre,post) if t)
    public=[t for t in session.transcript if t.phase not in ('pre','post')]
    keep={t.id for t in private+public[-(30-len(private)):]}
    for card in session.cards:
        turn=next((t for t in reversed(public) if t.persona_id==card.id),None)
        if turn and turn.id not in keep:
            removable=next((t for t in public if t.id in keep and sum(x.persona_id==t.persona_id and x.id in keep for x in public)>1),None)
            if removable: keep.remove(removable.id); keep.add(turn.id)
    selected=[t for t in session.transcript if t.id in keep]
    def excerpt(text,limit=260):
        return text if len(text)<=limit else text[:limit//2]+' …[중간 생략]… '+text[-limit//2:]
    excerpts=[f'{t.id}|{t.persona_id}|{t.phase}|{t.round}|{t.stance}: {excerpt(t.content)} / 이유: {excerpt(t.reason,100)} / 미확인: {"; ".join(t.unresolved_issues[:2])[:120]} / rules: {",".join(t.reasoning_rule_ids)}' for t in selected]
    report=llm.call('report',{'brief':brief_payload(session.brief),
                  'targets':[{'id':c.id,'segment':c.immutable_core.identity_context.segment,
                      'buying_role':c.immutable_core.decision_model.buying_role,
                      'expected_alternative':c.immutable_core.problem_context.current_alternative} for c in session.cards],
                  'transcript':excerpts,'transcript_format':'ID|persona|phase|round|stance: head/tail excerpt / reason / unknowns / rules. Incomplete excerpts: inspect full stored turns before treating conditions as agreement.',
                  'omitted_utterance_count':len(session.transcript)-len(selected),
                  'sources':[{'id':e.source_id,'level':int(e.level)} for e in session.input.evidence],
                  'sections':SECTIONS},Report,max_tokens=1100)
    report.notice='AI 시뮬레이션 가설입니다. 실제 시장 검증이나 구매 확정이 아닙니다.'
    flagged=[t.id for t in selected if t.quality_flags]
    if flagged: report.notice+=' 근거 제한으로 교정된 발화: '+', '.join(flagged)+'. 원문 자료와 대조하세요.'
    if len(selected)<len(session.transcript): report.notice+=' 긴 대화에서는 비공개 전·후 의견과 최근 공개 발화 중심으로 정리했습니다. 전체 대화는 JSON에 보존됩니다.'
    turns={t.id for t in selected}; sources={e.source_id:e for e in session.input.evidence}
    for name,rows in report.sections.items():
        for row in rows:
            if not set(row.utterance_ids)<=turns or not set(row.evidence_ids)<=set(sources): raise ValueError('report invented references')
            if name!='Real Interview Next Steps' and not row.utterance_ids: raise ValueError('report observation needs utterance IDs')
            row.evidence_level=min(sources[x].level for x in row.evidence_ids) if row.evidence_ids else EvidenceLevel.L0
            if not row.evidence_ids: row.confidence='low'
    return guard_report_quantities(session,guard_report_consensus(session,report),
        revision=sum(t.phase=='group' for t in session.transcript))
