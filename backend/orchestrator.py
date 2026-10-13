from .context import ContextManager,PersonaAgent,fingerprint
from .prompts import ROUNDS,PRE,POST
from .schemas import Utterance
from .services import generate_report

class TurnController:
    def score(self,agent,question,public,step,last_spoke,agents):
        core=agent.card.immutable_core
        profile=core.identity_context.use_context+' '+core.decision_model.buying_role
        relevance=sum(w in profile for w in question.split())/max(1,len(question.split()))
        disagreement=any(other.state.stance not in ('unknown',agent.state.stance) for other in agents.values())
        recent=public.recent[-1]['content'] if public.recent else ''
        mention=int(agent.card.id in recent or core.identity_context.segment in recent)
        unresolved=min(len(agent.state.unresolved_issues),3)/3
        penalty=2/max(1,step-last_spoke.get(agent.card.id,-10))
        return relevance+int(disagreement)+mention+unresolved-penalty
    def select(self,available,agents,question,public,step,last_spoke):
        return sorted(available,key=lambda pid:(-self.score(agents[pid],question,public,step,last_spoke,agents),pid))[0]

class Orchestrator:
    def __init__(self,llm): self.llm=llm; self.controller=TurnController()
    def run(self,s,save=lambda s:None,max_tokens=240,seed=42,repair=True):
        if s.protocol_version=='3':
            from .adaptive import AdaptiveConversation
            return AdaptiveConversation(self.llm,self.controller).run(s,save,max_tokens=max(360,max_tokens),seed=seed,repair=repair)
        if not 1<=len(s.cards)<=3: raise ValueError('1-3 validated cards required')
        agents={c.id:PersonaAgent(c,self.llm) for c in s.cards}; public=ContextManager(recent=6,summary_chars=900)
        last_spoke={}; hashes={c.id:fingerprint(c) for c in s.cards}
        def state(name): s.status=name; s.state_history.append(name); save(s)
        existing=list(s.transcript); cursor=0
        def speak(pid,phase,round_name,question,scores=None,reply=None):
            nonlocal cursor
            if cursor<len(existing):
                t=existing[cursor]; cursor+=1
                if (t.phase,t.round)!=(phase,round_name): raise ValueError('Saved protocol differs; create a new session for this protocol')
                pid=t.persona_id; agent=agents[pid]
                previous=agent.state.stance
                if previous not in ('unknown',t.stance) and t.reason!='UNKNOWN':
                    agent.state.revisions=(agent.state.revisions+[f'{previous}→{t.stance}: {t.reason}'])[-8:]
                agent.state.stance=t.stance; agent.state.reasons=[t.reason]; agent.state.unresolved_issues=list(t.unresolved_issues)
                agent.context.add(t)
                if phase=='group': public.add(t)
                s.states[pid]=agent.state.model_copy(deep=True)
                return pid
            # First opinions remain independent until the Cross-reaction round.
            visible=public if phase=='post' or (phase=='group' and round_name not in ('Problem Reality','Solution Reaction')) else None
            s.pending_question=question; s.pending_speaker=pid; save(s)
            a=agents[pid].answer(s.brief,phase,round_name,question,visible,max_tokens,seed,repair)
            if reply and visible and any(t['id']==reply for t in visible.recent): a.reply_to=reply
            t=Utterance(**a.model_dump(),id=f'u{len(s.transcript)+1}',persona_id=pid,phase=phase,round=round_name,question=question,
                        directed_to=pid,selection_reason='Moderator nomination; complete this question-answer pair before the next turn',speaker_scores=scores or {})
            s.transcript.append(t); agents[pid].context.add(t)
            if phase=='group': public.add(t)
            s.states[pid]=agents[pid].state.model_copy(deep=True); s.pending_question=None; s.pending_speaker=None; save(s)
            cursor+=1; return pid
        state('PRE')
        for pid in agents: speak(pid,'pre','Private Pre',PRE)
        state('GROUP')
        for rnd,question in ROUNDS:
            available=list(agents)
            for k in range(max(2,len(agents))):
                if not available: available=list(agents)
                step=cursor
                pid=self.controller.select(available,agents,question,public,step,last_spoke)
                scores={x:round(self.controller.score(agents[x],question,public,step,last_spoke,agents),4) for x in available}
                addressed=question; reply=None
                if rnd in ('Cross-reaction','Conflict Probe'):
                    peer=next((t for t in reversed(public.recent) if t['persona_id']!=pid),None)
                    if peer:
                        reply=peer['id']
                        addressed=f"{pid}에게 질문: {peer['persona_id']}의 공개 발화 [{reply}] ‘{peer['content'][:180]}’를 자신의 조건과 비교하세요. {question} 먼저 이 질문에 답하고 타인의 경험을 자신의 경험으로 말하지 마세요."
                actual=speak(pid,'group',rnd,addressed,scores,reply)
                if actual in available: available.remove(actual)
                last_spoke[actual]=step
        state('POST')
        for pid in agents: speak(pid,'post','Private Post',POST)
        if any(fingerprint(c)!=hashes[c.id] for c in s.cards): raise ValueError('immutable core mutation')
        state('REPORT'); s.report=generate_report(s,self.llm); state('COMPLETE')
        return s

    def ask(self,s,question,persona_id=None,save=lambda s:None,interaction='auto'):
        from .adaptive import AdaptiveConversation
        return AdaptiveConversation(self.llm,self.controller).ask(s,question,persona_id,save,interaction)
