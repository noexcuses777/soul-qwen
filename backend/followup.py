"""Grounded next-question planning. Never substitute a template for failed reasoning."""
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from .context import fingerprint
from .schemas import FollowupPlan, FollowupReview, FollowupRecommendation
from .services import brief_payload
from .quantities import quantity_texts, unsupported_quantities


def normalized(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC',text).casefold())


def repeated(question, previous):
    a,b=normalized(question),normalized(previous)
    if not a or not b: return False
    if a==b: return True
    if min(len(a),len(b))>=24 and (a in b or b in a): return True
    if min(len(a),len(b))<12: return False
    if SequenceMatcher(None,a,b).ratio()>=.84: return True
    grams=lambda x:{x[i:i+2] for i in range(len(x)-1)}
    x,y=grams(a),grams(b)
    return 2*len(x&y)/max(1,len(x)+len(y))>=.8


def safe(turn):
    return not any(flag.endswith(('_withheld','_unresolved')) for flag in turn.quality_flags)


def vague_method_request(text):
    """A meta request is not an interview prompt or an observed data requirement."""
    return bool(re.search(r'(?:구체적(?:인|으로)?\s*)?(?:방법|방안)(?:이나|\s*또는|과|/)?\s*(?:기준)?\s*(?:을|를)?\s*(?:알려|설명|제시)',text)
                or re.search(r'구체적인\s*(?:방법|방안)(?:이나|\s*또는|과|/)\s*기준\s*$',text))


def distinct(items):
    result=[]
    for item in items:
        value=item.strip()
        if value and not any(repeated(value,old) for old in result): result.append(value)
    return result


def context(session):
    public=[t for t in session.transcript if t.phase=='group']
    thread=session.threads[-1] if session.threads else None
    current=[t for t in public if thread and t.id in thread.utterance_ids]
    latest={t.persona_id:t for t in current}
    # Superseded/withheld assertions never become the evidence for a new proposal.
    visible=[t for t in latest.values() if safe(t)]
    older=[t for t in public[-12:] if safe(t) and t.id not in {x.id for x in visible}]
    history=session.dialogue_runtime.get('question_recommendation_history',[])
    asked=[{'id':t.id,'question':t.question} for t in session.threads]
    asked += [{'id':'event','question':e['content']} for e in session.chat_events if e.get('role')=='founder']
    offered=[{'id':x.get('id','offer'),'question':x['question'],'issue':x.get('issue',''),
              'angle':x.get('angle',''),'new_condition':x.get('new_condition','')} for x in history if x.get('question')]
    offered += [{'id':q.id,'question':q.question} for q in session.suggestions]
    offered += [{'id':t.id,'question':t.followup_question} for t in public if t.followup_question]
    prior=[]; seen=set()
    for item in asked+offered:
        signature=normalized(item['question'])
        if signature not in seen: prior.append(item); seen.add(signature)
    # Full strings stay server-side for all-history validation. A finite model view may
    # abstain, and must never claim older omitted question intents have been checked.
    exclusions=[{**item,'question':item['question'][:220]} for item in prior[-32:]]
    payload={'brief':brief_payload(session.brief),'root_question':thread.question if thread else '',
        'stop_reason':thread.stop_reason if thread else '',
        'latest_public':[{'id':t.id,'persona_id':t.persona_id,'content':t.content[:650],
            'reason':t.reason,'stance':t.stance,'unresolved_issues':t.unresolved_issues,
            'followup_kind':t.followup_kind,'followup_question':t.followup_question} for t in visible],
        'earlier_public_excerpts':[{'id':t.id,'persona_id':t.persona_id,'content':t.content[:160],
            'hypothesis':True} for t in older[-3:]],
        'participants':[{'id':c.id,'role':c.immutable_core.decision_model.buying_role,
            'current_alternative':c.immutable_core.problem_context.current_alternative,
            'adoption_barrier':c.immutable_core.decision_model.adoption_barrier,
            'switching_cost':c.immutable_core.decision_model.switching_cost,
            'budget_constraint':c.immutable_core.decision_model.budget_constraint,
            'reasoning_rules':[r.model_dump(mode='json') for r in c.immutable_core.reasoning_rules]} for c in session.cards],
        'previous_questions_and_offers':exclusions,'omitted_older_question_count':max(0,len(prior)-32)}
    return payload,public,visible,prior


def recommend(session,llm):
    payload,public,visible,prior=context(session)
    revision=len(public)
    identity={'policy':'followup-v1.1','revision':revision,'thread':session.threads[-1].id if session.threads else None,
        'cards':[fingerprint(c) for c in session.cards],'input':session.input.model_dump(mode='json')}
    key=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    cached=session.dialogue_runtime.get('next_question_cache',{})
    if cached.get('key')==key: return FollowupRecommendation.model_validate(cached['recommendation'])
    rid='fq-'+key[:16]
    audit={'revision':revision,'rejected':[]}
    def done(status,question,why,refs=(),missing=(),candidate=None):
        result=FollowupRecommendation(id=rid,revision=revision,status=status,question=question,
            why=why,source_utterance_ids=list(refs),missing_information=list(missing)[:4])
        session.dialogue_runtime['next_question_cache']={'key':key,'recommendation':result.model_dump(mode='json'),'audit':audit}
        if status=='discussion':
            session.dialogue_runtime.setdefault('question_recommendation_history',[]).append({
                **result.model_dump(mode='json'),'issue':candidate.issue,'angle':candidate.angle,
                'new_condition':candidate.new_condition})
        return result
    if not visible:
        return done('no_new_question','','추가 질문을 뒷받침할 최신 공개 발언이 없습니다. 구체적인 상황이나 자료를 먼저 알려주세요.')
    if len(prior)>32:
        # Refuse to certify semantic novelty against history the model cannot see.
        return done('no_new_question','','이미 다룬 질문이 많아 새 쟁점을 안전하게 구분하기 어렵습니다. 새 상황이나 조건을 직접 지정해 주세요.')
    plan=llm.call('followup_plan',payload,FollowupPlan,max_tokens=1000)
    visible_ids={t.id for t in visible}
    numeric_basis=quantity_texts(session.brief,[c.immutable_core for c in session.cards],session.input.evidence,[t.question for t in session.threads])
    eligible=[]
    for candidate in plan.candidates:
        text='\n'.join([candidate.question,candidate.why,candidate.issue,candidate.angle,candidate.new_condition])
        issue=None
        if not set(candidate.source_utterance_ids)<=visible_ids: issue='invalid_or_superseded_public_reference'
        elif any(repeated(candidate.question,x['question']) for x in prior): issue='repeated_question'
        elif any(all(repeated(getattr(candidate,k),x.get(k,'')) for k in ('issue','angle','new_condition'))
                 for x in session.dialogue_runtime.get('question_recommendation_history',[])): issue='repeated_answer_variable'
        elif any(repeated(candidate.question,x.question) for x in eligible): issue='repeated_candidate'
        elif unsupported_quantities(text,numeric_basis): issue='unsupported_numeric_premise'
        if issue: audit['rejected'].append({'question':candidate.question,'reason':issue})
        else: eligible.append(candidate)
    if eligible:
        review_payload={**payload,'candidates':[{'index':i,**c.model_dump(mode='json')} for i,c in enumerate(eligible)]}
        review=llm.call('followup_review',review_payload,FollowupReview,max_tokens=600)
        indices=[r.index for r in review.reviews]
        if len(indices)!=len(eligible) or set(indices)!=set(range(len(eligible))):
            audit['rejected'].append({'reason':'incomplete_semantic_review'})
        else:
            for verdict in sorted(review.reviews,key=lambda r:r.index):
                candidate=eligible[verdict.index]
                if verdict.novel and verdict.answerable:
                    return done('discussion',candidate.question,candidate.why,candidate.source_utterance_ids,candidate=candidate)
                audit['rejected'].append({'question':candidate.question,'reason':verdict.why,
                    'novel':verdict.novel,'answerable':verdict.answerable})
    evidence_question=plan.evidence_question.strip()
    if vague_method_request(evidence_question) or any(repeated(evidence_question,x['question']) for x in prior) or unsupported_quantities(evidence_question,numeric_basis):
        evidence_question=''
    missing=distinct([item for item in plan.missing_information if not vague_method_request(item)
                      and not unsupported_quantities(item,numeric_basis)])
    if missing:
        why=plan.why
        if why.rstrip().endswith(('?','？')) or normalized(why)==normalized(plan.evidence_question):
            why=f'다음 판단에는 {missing[0]}에 대한 실제 확인이 필요합니다.'
            if len(why)>220: why='현재 쟁점에 관한 실제 관찰 자료가 필요하여 가상 대화로 추가 판단을 보류합니다.'
        return done('needs_evidence',evidence_question,why,missing=missing)
    return done('no_new_question','',
        '현재 답변과 이전 질문을 비교했지만, 새로운 조건을 다룰 유용한 후속 질문을 확인하지 못했습니다.')
