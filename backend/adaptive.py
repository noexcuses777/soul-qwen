"""Bounded content-responsive conversation; v2 remains a controlled eval baseline."""
import re
from .context import ContextManager,PersonaAgent,fingerprint
from .schemas import Utterance
from .prompts import ROUNDS,PRE,POST
from .services import generate_report

class AdaptiveConversation:
    def __init__(self,llm,controller): self.llm=llm; self.controller=controller

    def restore(self,s):
        self.s=s; self.agents={c.id:PersonaAgent(c,self.llm) for c in s.cards}
        self.public=ContextManager(recent=6,summary_chars=900)
        self.last={}
        for i,t in enumerate(s.transcript):
            if t.persona_id in self.agents: self.agents[t.persona_id].context.add(t)
            if t.phase=='group': self.public.add(t); self.last[t.persona_id]=i
        for pid,state in s.states.items():
            if pid in self.agents: self.agents[pid].state=state.model_copy(deep=True)

    def event(self,content,role='moderator'):
        self.s.chat_events.append({'before':len(self.s.transcript),'role':role,'content':content})

    def select(self,question,exclude=None,inclusion=False):
        ids=[p for p in self.agents if p!=exclude] or list(self.agents)
        if inclusion:
            counts={p:sum(t.phase=='group' and t.persona_id==p for t in self.s.transcript) for p in ids}
            minimum=min(counts.values()); ids=[p for p in ids if counts[p]==minimum]
        return self.controller.select(ids,self.agents,question,self.public,len(self.s.transcript),self.last)

    @staticmethod
    def repeated_question(question,previous):
        def grams(text):
            clean=re.sub(r'\W','',text.lower())
            return {clean[i:i+3] for i in range(max(0,len(clean)-2))}
        a,b=grams(question),grams(previous)
        return bool(a and b and 2*len(a&b)/(len(a)+len(b))>=.6)

    def speak(self,pid,phase,topic,question,save,reply=None,max_tokens=360,seed=42,repair=True,conversation_step=None,snapshot_revision=None):
        s=self.s; s.pending_question=question; s.pending_speaker=pid; save(s)
        active=s.dialogue_runtime.get('followup',{}).get('thread_id') if phase=='post' or phase=='group' and topic=='Founder Follow-up' else None
        thread=next((t for t in s.threads if t.id==active),None)
        if phase=='post' and thread:
            public=[t for t in s.transcript if t.phase=='group']
            visible={t.id for t in (public if snapshot_revision is None else public[:snapshot_revision])}
            if not thread.utterance_ids or not set(thread.utterance_ids)<=visible: thread=None
        goal=thread.question if thread else None
        parent=next((t for t in s.transcript if t.id==reply and t.phase=='group'),None) if conversation_step else None
        parent_payload={k:v for k,v in parent.model_dump(mode='json').items()
                        if k in ('id','persona_id','phase','content','stance','reason','unresolved_issues','reasoning_rule_ids')} if parent else None
        if parent_payload:
            peer=self.agents[parent.persona_id].card
            parent_payload.update(speaker_alias=peer.presentation.display_name,
                hypothetical_role=peer.immutable_core.decision_model.buying_role,
                expected_alternative=peer.immutable_core.problem_context.current_alternative)
            parent_payload['reasoning_rule_ids']=[peer.id+':'+rid for rid in parent.reasoning_rule_ids]
            parent_payload['reasoning_rules']=[{'id':peer.id+':'+r.id,'value':r.value,'tradeoff':r.tradeoff,'conditional_choice':r.conditional_choice}
                for r in peer.immutable_core.reasoning_rules if r.id in parent.reasoning_rule_ids]
        a=self.agents[pid].answer(s.brief,phase,topic,question,self.public if phase in ('group','post') else None,
            max_tokens,seed,repair,interaction=phase=='group',participants=list(self.agents),
            participant_names={c.id:c.presentation.display_name for c in s.cards},dialogue_goal=goal,
            private_baseline=next(({'content':t.content,'stance':t.stance,'reason':t.reason} for t in s.transcript
                if t.phase=='pre' and t.persona_id==pid),None) if phase=='post' or conversation_step else None,
            conversation_step=conversation_step,required_parent=parent_payload,
            participant_profiles={c.id:{'role':c.immutable_core.decision_model.buying_role} for c in s.cards},
            active_thread_id=thread.id if thread else None)
        # Controller assigns only an actually visible public reply; never a private utterance.
        a.reply_to=reply if parent or reply and any(x['id']==reply for x in self.public.recent) else None
        scores={p:round(self.controller.score(self.agents[p],question,self.public,len(s.transcript),self.last,self.agents),4) for p in self.agents}
        t=Utterance(**a.model_dump(),id=f'u{len(s.transcript)+1}',persona_id=pid,phase=phase,round=topic,question=question,
            directed_to=getattr(a,'addressed_to',None),snapshot_revision=snapshot_revision,selection_reason='Directed response/clarification to a visible public utterance' if reply else 'Inclusion, relevance, contrast, unresolved issues and recent speaking penalty',speaker_scores=scores)
        if thread and conversation_step: t.thread_id=thread.id
        s.transcript.append(t); self.agents[pid].context.add(t)
        if phase=='group': self.public.add(t); self.last[pid]=len(s.transcript)-1
        s.states[pid]=self.agents[pid].state.model_copy(deep=True)
        s.pending_question=None; s.pending_speaker=None
        return t

    def reaction(self,t,depth):
        """One pending adjacency pair. Bounded expansion prevents circular questioning."""
        if depth>=3 or len(self.agents)<2 or t.dialogue_act=='close' or 'response_repeat_unresolved' in t.quality_flags: return None
        prior=next((x for x in reversed(self.s.transcript[:-1]) if x.id==t.reply_to),None)
        needs=t.dialogue_act in ('question','clarify','disagree') or bool(t.followup_question)
        if not prior and (t.unresolved_issues or t.stance=='conditional'): needs=True
        if not needs: return None
        if t.followup_question and any(self.repeated_question(t.followup_question,x.followup_question) for x in self.s.transcript[-9:-1] if x.phase=='group' and x.followup_question):
            self.event('비슷한 확인 질문이 반복되어 다음 의제로 이동합니다. 확인되지 않은 조건은 미해결 항목으로 남깁니다.')
            return None
        pid=t.addressed_to if t.addressed_to in self.agents and t.addressed_to!=t.persona_id else (prior.persona_id if prior else self.select(t.followup_question or t.content,t.persona_id))
        if pid==t.persona_id: return None
        name=self.agents[t.persona_id].card.presentation.display_name or t.persona_id
        q=f"{name}님의 공개 발화 [{t.id}]: {t.content[:180]}\n{t.followup_question or '이 조건 차이에 답하거나 오해를 정정해주세요. 억지 이견 없이 자신의 조건을 설명하세요.'}"
        return {'pid':pid,'question':q,'reply':t.id}

    def next_topic(self,r):
        visited=r.setdefault('visited',list(range(r['topic'])))
        available=[i for i in range(len(ROUNDS)) if i not in visited]
        if not visited: return 0
        signals=' '.join(x.get('content','') for x in self.public.recent[-2:])
        signals+=' '+' '.join(issue for a in self.agents.values() for issue in a.state.unresolved_issues)
        cues=[('문제','빈도','대안','상황'),('기능','해결','효과','도움','신뢰'),('비교','공통','적용','다른','역할'),
              ('차이','반대','오해','정정','동의'),('예산','가격','비용','구매','도입','지불','결정','전환'),('실패','중단','거절','포기','바꾸')]
        return max(available,key=lambda i:(sum(signals.count(w) for w in cues[i]),-i)) if available else None

    def run(self,s,save,max_tokens=360,seed=42,repair=True):
        if not 1<=len(s.cards)<=3: raise ValueError('1-3 validated cards required')
        self.restore(s); hashes={c.id:fingerprint(c) for c in s.cards}
        def state(value):
            s.status=value
            if not s.state_history or s.state_history[-1]!=value: s.state_history.append(value)
            save(s)
        state('PRE')
        for pid in self.agents:
            if not any(t.phase=='pre' and t.persona_id==pid for t in s.transcript):
                self.speak(pid,'pre','Private Pre',PRE,save,max_tokens=240,seed=seed,repair=repair); save(s)
        r=s.dialogue_runtime.setdefault('group',{'topic':0,'depth':0,'pending':None,'closing':False,'closed':[]})
        if not s.chat_events:
            self.event('가상 인터뷰를 시작합니다. 각자의 조건을 비교하며, 모르는 내용은 모른다고 답합니다. 실제 경험이나 구매 의사를 확인한 결과는 아닙니다.'); save(s)
        state('GROUP'); budget=18; reserve=len(self.agents)
        while not r['closing']:
            count=sum(t.phase=='group' and t.round!='Founder Follow-up' for t in s.transcript)
            if count>=budget-reserve or (r['topic']>=len(ROUNDS) and not r['pending']):
                r['closing']=True; r['close_reason']='대화 예산 상한' if count>=budget-reserve else '의제 확인 완료'
                self.event(f"{r['close_reason']}으로 마무리하려 합니다. 각자 남은 핵심 조건이나 정정할 점을 한 가지 알려주세요."); save(s); break
            pending=r['pending']
            if pending:
                pid=pending['pid']; question=pending['question']; reply=pending['reply']; topic=r['current_topic']
            else:
                idx=self.next_topic(r)
                if idx is not None:
                    topic,question=ROUNDS[idx]; r['topic']+=1
                    r['visited'].append(idx)
                else:
                    topic='Open clarification'; question='지금까지의 공개 대화에서 자신의 조건에 적용되지 않는 내용이나 아직 확인할 중요한 조건이 있나요? 없다면 없다고 말하세요.'
                pid=self.select(question,inclusion=True); reply=None; r['depth']=0; r['current_topic']=topic
                if topic in ('Cross-reaction','Conflict Probe'):
                    peer=next((x for x in reversed(self.public.recent) if x['persona_id']!=pid),None)
                    if peer:
                        reply=peer['id']; question+=f"\n비교할 공개 발화 [{reply}] {peer['persona_id']}: {peer['content'][:180]}"
                question+='\n이전 대화의 반복 질문 대신 지금 의제에 먼저 답하세요. 자신의 카드에 있는 역할과 조건을 명시하고 없는 사실은 UNKNOWN으로 남기세요.'
                self.event(question)
                # Persist the selected action so a failed model call resumes the same question.
                r['pending']={'pid':pid,'question':question,'reply':reply}; save(s)
            t=self.speak(pid,'group',topic,question,save,reply,max_tokens,seed,repair)
            r['depth']+=1
            remaining=len(ROUNDS)-min(r['topic'],len(ROUNDS))
            r['pending']=self.reaction(t,r['depth']) if count+1+remaining<budget-reserve else None
            save(s)
        while len(r['closed'])<len(self.agents) or r.get('close_pending'):
            pending=r.get('close_pending')
            if pending:
                t=self.speak(pending['pid'],'group','Closing clarification',pending['question'],save,pending['reply'],max_tokens,seed,repair)
                r['close_pending']=None
            else:
                pid=next(p for p in self.agents if p not in r['closed'])
                t=self.speak(pid,'group','Closing check','이 대화를 마무리하기 전에 남은 핵심 질문이나 정정할 점을 한 가지 말해주세요. 없다면 없다고 답하세요.',save,max_tokens=max_tokens,seed=seed,repair=repair)
                r['closed'].append(pid)
                count=sum(x.phase=='group' and x.round!='Founder Follow-up' for x in s.transcript)
                if count+(len(self.agents)-len(r['closed']))<budget: r['close_pending']=self.reaction(t,1)
            save(s)
        if not r.get('ended'):
            self.event('공개 대화를 마쳤습니다. 남은 질문은 실제 고객 인터뷰로 이어가겠습니다. 이제 타인의 답을 공개하지 않고 개인별 최종 판단을 받습니다.'); r['ended']=True; save(s)
        state('POST')
        for pid in self.agents:
            if not any(t.phase=='post' and t.persona_id==pid for t in s.transcript):
                self.speak(pid,'post','Private Post',POST,save,max_tokens=240,seed=seed,repair=repair); save(s)
        if any(fingerprint(c)!=hashes[c.id] for c in s.cards): raise ValueError('immutable core mutation')
        state('REPORT'); s.report=generate_report(s,self.llm); state('COMPLETE'); return s

    def ask(self,s,question,persona_id,save,interaction='auto'):
        self.restore(s)
        if persona_id and persona_id not in self.agents: raise ValueError('Unknown persona')
        r=s.dialogue_runtime.get('followup')
        key=[question,persona_id,interaction]
        if r and not r.get('done') and r['key']!=key: raise ValueError('미완료 추가 질문을 같은 내용·참여자·방식으로 재개하세요.')
        s.error=None
        if not r or r.get('done'):
            pid=persona_id or self.select(question)
            r={'key':key,'count':0,'pending':{'pid':pid,'question':question,'reply':None},'done':False}
            s.dialogue_runtime['followup']=r; self.event(question,'founder'); save(s)
        while r['pending'] and r['count']<4:
            p=r['pending']; t=self.speak(p['pid'],'group','Founder Follow-up',p['question'],save,p['reply'])
            r['count']+=1
            r['pending']=None if interaction=='direct' else self.reaction(t,r['count'])
            if r['count']==1 and len(self.agents)>1 and (interaction=='interactive' or (interaction=='auto' and t.unresolved_issues)) and not r['pending']:
                pid=self.select(t.content,t.persona_id)
                r['pending']={'pid':pid,'question':f'{t.persona_id}님의 답변 [{t.id}]: {t.content[:180]}\n자신의 조건에서 적용되는 점이나 다른 조건을 구체적으로 짚으세요. 차이가 없다면 동의하세요. 필요한 확인 질문만 하세요.','reply':t.id}
            save(s)
        if not r.get('answered'):
            self.event('추가 질문의 응답을 마쳤습니다. 확인되지 않은 조건은 다음 질문이나 실제 인터뷰로 이어갈 수 있습니다.'); r['answered']=True; save(s)
        s.report=generate_report(s,self.llm); r['done']=True; s.error=None; save(s); return s
