import hashlib,json,re,copy
from difflib import SequenceMatcher
from .schemas import SessionState
from .quantities import quantity_texts, unsupported_quantities

def fingerprint(card):
    return hashlib.sha256(card.immutable_core.model_dump_json().encode()).hexdigest()

class ContextManager:
    """Independent owned/private buffer and separately attributed public observations."""
    def __init__(self,recent=6,summary_chars=900):
        self.recent_limit=recent; self.summary_chars=summary_chars
        self.recent=[]; self.summary=''
    def add(self,turn):
        self.recent.append(turn.model_dump(mode='json') if hasattr(turn,'model_dump') else dict(turn))
        while len(self.recent)>self.recent_limit:
            old=self.recent.pop(0)
            line=f"[{old['id']} {old['persona_id']} {old['phase']}] {old['content'][:180]} | reason: {old.get('reason','UNKNOWN')[:100]}\n"
            lines=(self.summary+line).splitlines(keepends=True)
            while len(''.join(lines))>self.summary_chars and lines: lines.pop(0)
            self.summary=''.join(lines)
    def view(self):
        keys=('id','persona_id','phase','round','content','stance','reason','reply_to')
        return {'older_summary':self.summary,'recent':[{k:t[k] for k in keys if k in t} for t in self.recent]}

class PersonaAgent:
    def __init__(self,card,llm):
        self.card=card.model_copy(deep=True); self.llm=llm
        self.core_hash=fingerprint(self.card); self.context=ContextManager(recent=4,summary_chars=600)
        self.state=SessionState.model_validate(card.session_state.model_dump())
    def answer(self,brief,phase,round_name,question,public=None,max_tokens=350,seed=42,repair=True,interaction=False,participants=None,participant_names=None,dialogue_goal=None,private_baseline=None,conversation_step=None,required_parent=None,participant_profiles=None,active_thread_id=None):
        from .schemas import AgentAnswer,InteractionAnswer
        if fingerprint(self.card)!=self.core_hash: raise ValueError('immutable core changed')
        from .services import brief_payload
        card=self.card.model_dump(mode='json'); card.pop('session_state',None)
        card.pop('presentation',None)
        payload={'brief':brief_payload(brief),'card':card,
                 'state':self.state.model_dump(mode='json'),'own':self.context.view(),
                 'group':public.view() if public else {'older_summary':'','recent':[]},
                 'phase':phase,'round':round_name,'question':question}
        if round_name=='Closing check':
            # Closing is an individual correction opportunity, not another peer-question chain.
            payload['group']={'older_summary':'','recent':[]}
            payload['state']={'stance':self.state.stance}
            dialogue_goal=question
        if phase=='post':
            payload['private_baseline']=private_baseline
            payload['human_question']=dialogue_goal
            payload['group']={'older_summary':'','recent':[t for t in payload['group']['recent']
                if t.get('round')!='Closing check' and t.get('persona_id')!=self.card.id][-3:]}
        if interaction:
            payload['participants']=participants or []
            if participant_names: payload['participant_aliases']=participant_names
            if dialogue_goal: payload['dialogue_goal']=dialogue_goal
        if conversation_step: payload['conversation_step']=conversation_step
        if conversation_step:
            c=self.card.immutable_core
            # Local r1/r2 IDs recur across cards. Model-visible IDs must identify their owner.
            for rule in card['immutable_core'].get('reasoning_rules',[]): rule['id']=self.card.id+':'+rule['id']
            current=[t for t in self.context.recent if t.get('phase')=='group' and
                     (t.get('thread_id')==active_thread_id if active_thread_id else t.get('question')==dialogue_goal)]
            previous=[t for t in self.context.recent if t.get('phase')=='group' and t not in current][-2:]
            payload['own']={'older_summary':'Earlier generated views are hypotheses, never new persona traits or evidence.',
                'recent':[{k:t[k] for k in ('id','persona_id','phase','stance','content') if k in t} for t in current[-2:]],
                'prior_view_excerpts':[{'id':t['id'],'content':t['content'][:120],'hypothesis':True} for t in previous]}
            payload['state']={'stance':self.state.stance,'note':'Previous generated reasons are not immutable preferences. Use the card for current reasoning.'}
            payload['private_baseline']=private_baseline
            payload['own_decision_frame']={'persona_id':self.card.id,'hypothetical_role':c.decision_model.buying_role,
                'expected_alternative':c.problem_context.current_alternative,'exposure':c.identity_context.use_context,
                'rules':[{'id':self.card.id+':'+r.id,'trigger':r.trigger,'value':r.value,'tradeoff':r.tradeoff,
                          'conditional_choice':r.conditional_choice} for r in c.reasoning_rules],
                'instruction':'Only this frame describes YOU. A parent is a different speaker, never your alternative/history.'}
            if conversation_step=='contribution':
                # Publish independent first views before exposing them to peer influence.
                payload['group']={'older_summary':'','recent':[]}
                required_parent=None
            else:
                # Only the current public parent is observed in full. All other speakers remain
                # in the saved transcript, rather than becoming competing anonymous premises.
                payload['group']={'older_summary':'','recent':[]}
        if required_parent:
            if required_parent.get('phase')!='group': raise ValueError('Required parent must be public')
            payload['required_parent']=copy.deepcopy(required_parent)
        task='chat' if conversation_step else 'interact' if interaction else 'agent'
        answer_schema=InteractionAnswer if interaction else AgentAnswer
        # A peer's question/previous generated view is never numeric evidence.
        human_question=dialogue_goal or (question if round_name=='Founder Follow-up' and not required_parent else '')
        numeric_basis=quantity_texts(self.card.immutable_core,brief,human_question)
        # Filter only the model-facing copy; saved generated views remain intact for audit.
        for key in ('recent','prior_view_excerpts'):
            views=payload['own'].get(key,[])
            valid=[view for view in views if not unsupported_quantities('\n'.join(quantity_texts(view)),numeric_basis)]
            if len(valid)!=len(views):
                payload['own'][key]=valid
                payload['own']['omitted_invalid_numeric_history']=True
        a=self.llm.call(task,payload,answer_schema,max_tokens=max_tokens,seed=seed,repair=repair)
        a.quality_flags=[]; a.generated_content=None
        def repeats(text):
            normalized=lambda x:re.sub(r'\W','',x.lower())
            return len(normalized(text))>=30 and any(SequenceMatcher(None,normalized(text),normalized(t.get('content',''))).ratio()>=.85
                for t in (self.context.recent[-2:]+(public.recent[-3:] if public else [])))
        def unsafe(text):
            purchase=bool(re.search(r'(구매하겠습니다|결제하겠습니다|구매할게|구매 의[사향]가 (확실|높)|도입하겠습니다)',text))
            past=not self.card.immutable_core.evidence_anchors and bool(re.search(r'(사용해\s?봤|써\s?봤|겪었|직접 경험했|현재.{0,30}사용\s?중|저는.{0,25}(사용합니다|사용 중|쓰며|씁니다))',text))
            return 'purchase_overclaim' if purchase else 'unsupported_experience' if past else None
        def quantity_issue(answer):
            text='\n'.join([answer.content,answer.reason,*answer.unresolved_issues,getattr(answer,'followup_question','')])
            return 'unsupported_quantity' if unsupported_quantities(text,numeric_basis) else None
        def perspective_issue(text):
            if not conversation_step: return None
            norm=lambda x:re.sub(r'\W','',x)
            own_role=norm(self.card.immutable_core.decision_model.buying_role)
            claims=re.findall(r'(?:저는|제가|저의 역할은|제 역할은)[^.!?\n]{0,25}',text)
            other_roles=[norm(p.get('role','')) for pid,p in (participant_profiles or {}).items()
                if pid!=self.card.id and p.get('role') not in ('UNKNOWN','',None)]
            def ascribes(claim,role):
                text=norm(claim)
                # Referencing a peer's condition is allowed; require an explicit self-ascription.
                if any(marker in text for marker in ('님','동료','상대','다른참여자')): return False
                return bool(re.search(re.escape(role)+r'(?:로서|역할을맡|역할로|입니다|이며|이고|이므로|인만큼)',text))
            if any(role and role!=own_role and own_role not in norm(claim) and ascribes(claim,role)
                   for role in other_roles for claim in claims):
                return 'persona_identity_mismatch'
            own_name=self.card.presentation.display_name
            if required_parent and own_name and own_name+'님' in text:
                return 'persona_self_address'
            return None
        repeat=repeats(a.content) if interaction and dialogue_goal else False
        issue=quantity_issue(a) or unsafe(a.content) or perspective_issue(a.content)
        should_repair=(interaction and dialogue_goal and (repeat or (conversation_step and issue))) or issue=='unsupported_quantity'
        if repair and self.llm.mode=='qwen' and should_repair:
            original=a.content; revision=copy.deepcopy(payload)
            revision['own']={'older_summary':'','recent':[]}
            revision['group']={'older_summary':'','recent':payload['group']['recent'][-2:]}
            revision['state']={'stance':self.state.stance}
            revision['correction_request']={'candidate':
                'Unanchored numerical candidate withheld; regenerate from own card and human root question'
                if issue=='unsupported_quantity' else original,'issue':issue or 'Repeated earlier response',
                'own_role':self.card.immutable_core.decision_model.buying_role,
                'own_name':self.card.presentation.display_name,
                'parent_name':required_parent.get('speaker_alias') if required_parent else None,
                'instruction':'Answer the root question using OWN rule. Do not claim another role or address yourself as a peer. Respond to the actual named parent. Replace unsupported experience/purchase with conditional reasoning. Use quantities only from your own card, founder brief or current human root question. Remove absent thresholds from content, reason and follow-up questions. Peers and generated history cannot supply numeric evidence.'}
            a=self.llm.call(task,revision,answer_schema,max_tokens=max_tokens,seed=seed+1,repair=repair)
            a.generated_content=original
            a.quality_flags=(['response_repeat_unresolved' if repeats(a.content) else 'response_repetition_repaired'] if repeat else [issue+'_repaired' if not (quantity_issue(a) or unsafe(a.content) or perspective_issue(a.content)) else issue+'_unresolved'])
        rules={r.id:r for r in self.card.immutable_core.reasoning_rules}
        a.reasoning_rule_ids=[rid.removeprefix(self.card.id+':') for rid in a.reasoning_rule_ids]
        a.reasoning_rule_ids=[rid for rid in a.reasoning_rule_ids if rid in rules]
        mismatch=perspective_issue(a.content)
        if mismatch:
            if a.generated_content is None: a.generated_content=a.content
            a.quality_flags=(a.quality_flags+[mismatch+'_withheld'])[-4:]
            baseline=next((t for t in reversed(self.context.recent) if t.get('phase')=='group'
                and t.get('question')==dialogue_goal and not perspective_issue(t.get('content',''))),None)
            rule=next(iter(rules.values()),None)
            a.content=baseline['content'] if baseline else ('가설로는 '+rule.conditional_choice if rule else '제 조건을 확인할 근거가 부족하여 판단을 보류합니다.')
            a.reason='자기 역할/응답 대상 귀속 검사를 통과하지 못해 독립 판단을 유지하며 새 비교는 보류'
            a.stance=baseline.get('stance','conditional') if baseline else 'conditional'
            a.reasoning_rule_ids=baseline.get('reasoning_rule_ids',[]) if baseline else [rule.id] if rule else []
            a.dialogue_act='answer'; a.followup_question=''; a.followup_kind='none'; a.addressed_to=None
            a.unresolved_issues=(a.unresolved_issues+['동료 조건에 대한 새 판단의 귀속 검토 필요'])[-8:]
        # Narrow lexical guard, not a semantic faithfulness score. Preserve raw text for audit.
        issue=quantity_issue(a) or unsafe(a.content)
        if issue:
            if a.generated_content is None: a.generated_content=a.content
            a.quality_flags=(a.quality_flags+[issue])[-4:]
            rule=next((rules[rid] for rid in a.reasoning_rule_ids),None)
            if issue=='unsupported_quantity':
                a.content='수치 조건의 근거가 없어 판단을 보류합니다. 실제 빈도·비용·소요 조건을 확인한 뒤 비교해야 합니다.'
                a.reason='자기 카드·아이디어·현재 사용자 질문에서 확인되지 않은 수치 조건을 보류'
                a.unresolved_issues=['수치 조건의 실제 근거 확인']
                a.quality_flags=(a.quality_flags+['unsupported_quantity_withheld'])[-4:]
            else:
                a.content=('가설로는 '+rule.conditional_choice+' ' if rule else '제 조건에서 효과와 장벽을 확인해야 판단할 수 있습니다. ')
                a.content+='실제 경험이나 구매 의사를 확인한 답변은 아닙니다.'
                a.reason='확인되지 않은 경험·구매 확정 표현을 조건부 판단으로 교정'
            a.stance='conditional'
            if interaction: a.dialogue_act='answer'; a.followup_question=''; a.followup_kind='none'; a.addressed_to=None
            if issue!='unsupported_quantity': a.unresolved_issues=(a.unresolved_issues+['실제 경험·도입 조건 확인'])[-8:]
        if not self.card.immutable_core.evidence_anchors and not re.search(r'(가설|라면|다면|조건|가능성|모릅니다|알 수 없|미확인)',a.content):
            a.content='가상 조건에 따른 가설로는, '+a.content
        if interaction and a.addressed_to not in (participants or []): a.addressed_to=None
        if interaction and round_name=='Closing check':
            a.dialogue_act='close'; a.addressed_to=None; a.followup_question=''
        allowed={x['id'] for x in payload['group']['recent']}
        if required_parent: allowed.add(required_parent['id'])
        # Nullable fields are sometimes emitted as "UNKNOWN" by small local models.
        # Discard every reference that is not in the explicitly visible public buffer.
        if a.reply_to and a.reply_to not in allowed: a.reply_to=None
        known={x.source_id for x in self.card.immutable_core.evidence_anchors}
        a.evidence_ids=[source_id for source_id in a.evidence_ids if source_id in known]
        if a.stance != self.state.stance and self.state.stance!='unknown':
            if a.reason=='UNKNOWN':
                a.stance=self.state.stance
                a.unresolved_issues=(a.unresolved_issues+['입장 변화 이유 미제시'])[-8:]
            else:
                self.state.revisions=(self.state.revisions+[f'{self.state.stance}→{a.stance}: {a.reason}'])[-8:]
        self.state.stance=a.stance; self.state.reasons=[a.reason]; self.state.unresolved_issues=a.unresolved_issues
        return a
