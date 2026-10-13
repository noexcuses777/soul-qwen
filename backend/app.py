import os,threading,uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .schemas import *
from .llm import LLMClient,LLMError
from .services import parse_idea,generate_targets,build_card,validate_card,validate_target_selection
from .display_names import ensure_session_names
from .limits import LIMITS,check_input,check_target
from .orchestrator import Orchestrator
from .store import Store

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')

def create_app(db=None,llm=None):
    app=FastAPI(title='Persona Studio',version='0.1.0')
    client=llm or LLMClient(); store=Store(db or os.getenv('SESSION_DB',str(ROOT/'data/sessions.sqlite3')))
    lock=threading.Lock(); app.state.llm=client; app.state.store=store
    def get(id):
        try:
            return ensure_session_names(store.get(id))
        except KeyError: raise HTTPException(404,'Session not found')
    def acquire():
        if not lock.acquire(blocking=False): raise HTTPException(409,'Another local operation is running')
    def ensure_model():
        if client.mode=='qwen' and not client.health()['connected']:
            raise HTTPException(503,'Qwen 모델 서버 연결이 끊겼습니다. scripts/start_persona_studio_windows.ps1로 앱을 다시 시작하세요.')
    def input_check(i):
        try: check_input(i)
        except ValueError as exc: raise HTTPException(422,str(exc))
    @app.get('/api/health')
    def health():
        model_health=client.health()
        return {'status':'ok' if model_health['connected'] else 'degraded','mode':client.mode,
                'model':client.model,'model_server':model_health,'hypothesis_only':True}
    @app.get('/api/categories')
    def categories(): return CATEGORIES
    @app.get('/api/limits')
    def limits(): return LIMITS
    @app.get('/api/latest',response_model=Session | None)
    def latest():
        s=store.latest()
        return ensure_session_names(s) if s is not None else None
    @app.post('/api/brief',response_model=IdeaBrief)
    def brief(i:IdeaInput): input_check(i); return parse_idea(i)
    @app.post('/api/sessions',response_model=Session)
    def create(i:IdeaInput):
        input_check(i)
        ensure_model()
        acquire(); start=len(client.records)
        try:
            b=parse_idea(i); audits=[]; ts=generate_targets(b,i.evidence,client,audits)
            s=Session(id=uuid.uuid4().hex,input=i,brief=b,targets=ts,target_audits=audits,mode=client.mode,usage=client.usage(start),protocol_version='5')
            ensure_session_names(s,fresh_recommendation=True); store.put(s); return s
        except (ValueError,LLMError) as exc: raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.get('/api/sessions/{id}',response_model=Session)
    def read(id:str): return get(id)
    @app.get('/api/sessions/{id}/report-view')
    def read_report_view(id:str):
        from .report_view import report_view
        s=get(id)
        if s.report is None: raise HTTPException(409,'대화를 진행한 뒤 리포트를 먼저 생성하세요.')
        return report_view(s)
    @app.post('/api/sessions/{id}/targets/recommend',response_model=Session)
    def recommend_again(id:str):
        ensure_model(); acquire(); start=len(client.records)
        try:
            s=get(id)
            if s.status!='CREATED' or s.cards or s.transcript:
                raise HTTPException(409,'페르소나 생성 전에만 타깃을 다시 추천받을 수 있습니다. 새 아이디어 입력으로 시작하세요.')
            audits=[]; targets=generate_targets(s.brief,s.input.evidence,client,audits)
            s.target_audits.append(TargetAudit(stage='replaced',targets=s.targets))
            s.target_audits.extend(audits); s.targets=targets
            ensure_session_names(s,fresh_recommendation=True)
            s.usage.setdefault('target_recommendations',[]).append(client.usage(start)); store.put(s); return s
        except (ValueError,LLMError) as exc: raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.delete('/api/sessions/{id}')
    def delete(id:str):
        acquire()
        try: get(id); store.delete(id); return {'deleted':True}
        finally: lock.release()
    @app.post('/api/sessions/{id}/select',response_model=Session)
    def select(id:str,selection:Selection):
        ensure_model()
        acquire()
        try:
            s=get(id)
            if s.status not in ('CREATED','SELECTED'): raise HTTPException(409,'Create a new session to change an interview already started')
            lookup={t.id:t for t in s.targets}
            if not set(selection.target_ids)<=set(lookup): raise HTTPException(422,'unknown target ID')
            chosen=[lookup[x] for x in selection.target_ids]+selection.custom_targets
            if len({t.id for t in chosen})!=len(chosen):
                raise HTTPException(422,'같은 타깃을 중복 선택했습니다. 서로 다른 타깃을 선택하세요.')
            cards=[]; validations=[]; start=len(client.records)
            for t in chosen:
                check_target(t)
                if not set(t.evidence_ids)<={e.source_id for e in s.input.evidence}: raise HTTPException(422,'custom target invented evidence IDs')
                if not t.evidence_ids: t.evidence_level=EvidenceLevel.L0; t.confidence='low'
                elif t.evidence_level>min(e.level for e in s.input.evidence if e.source_id in t.evidence_ids): raise HTTPException(422,'custom target evidence level exceeds sources')
            selection_audit=validate_target_selection(s.brief,chosen,s.target_audits,client)
            for n,t in enumerate(chosen):
                card,audit=build_card(t,cards,s.input.evidence,client,f'p{n+1}',s.brief); cards.append(card); validations.append(audit)
                if selection.display_names: card.presentation.display_name=selection.display_names[t.id]
                elif t.id in s.target_display_names: card.presentation.display_name=s.target_display_names[t.id]
            if selection_audit: s.target_audits.append(selection_audit)
            s.cards=cards; s.validations=validations; s.status='SELECTED'; s.state_history.append('SELECTED')
            s.selected_target_ids=[t.id for t in chosen]
            ensure_session_names(s)
            s.suggestions=[]; s.lounge_mode=None
            s.usage['selection']=client.usage(start); store.put(s); return s
        except (ValueError,LLMError) as exc: raise HTTPException(422,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/run',response_model=Session)
    def run(id:str):
        ensure_model()
        acquire()
        try:
            s=get(id)
            if s.lounge_mode=='guided': raise HTTPException(409,'직접 질문 라운지는 start/ask/finish로 재개하세요.')
            if s.status not in ('SELECTED','FAILED','PRE','GROUP','POST','REPORT'): raise HTTPException(409,'Select targets first; completed interviews cannot be run again')
            if s.protocol_version in ('4','5'): s.protocol_version='3'; s.lounge_mode='moderated'
            s.error=None
            start=len(client.records)
            try:
                Orchestrator(client).run(s,store.put)
                s.usage['interview']=client.usage(start); store.put(s); return s
            except (ValueError,LLMError) as exc:
                s.status='FAILED'; s.state_history.append('FAILED'); s.error=str(exc)
                s.usage.setdefault('failed_interview_attempts',[]).append(client.usage(start)); store.put(s)
                raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/names/{persona_id}',response_model=Session)
    def rename(id:str,persona_id:str,edit:NameEdit):
        acquire()
        try:
            s=get(id); card=next((c for c in s.cards if c.id==persona_id),None)
            if card is None: raise HTTPException(422,'Unknown persona')
            if any(c.id!=persona_id and c.presentation.display_name==edit.display_name for c in s.cards): raise HTTPException(422,'참여자 이름은 서로 다르게 지정하세요.')
            card.presentation.display_name=edit.display_name; ensure_session_names(s); store.put(s); return s
        finally: lock.release()
    @app.post('/api/sessions/{id}/suggestions',response_model=Session)
    def suggest(id:str):
        from .guided import question_plan
        ensure_model(); acquire()
        try:
            s=get(id)
            if not s.cards: raise HTTPException(409,'Select personas first')
            if not s.suggestions:
                start=len(client.records); s.suggestions=question_plan(s,client)
                s.usage['suggestions']=client.usage(start); store.put(s)
            return s
        except (ValueError,LLMError) as exc: raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/next-question',response_model=FollowupRecommendation)
    def next_question(id:str,options:NextQuestionRequest=NextQuestionRequest()):
        from .followup import recommend
        ensure_model(); acquire()
        try:
            s=get(id); revision=sum(t.phase=='group' for t in s.transcript)
            if options.revision is not None and options.revision!=revision:
                raise HTTPException(409,'대화가 갱신되었습니다. 최신 답변에서 후속 질문을 다시 검토하세요.')
            followup=s.dialogue_runtime.get('followup'); snapshot=s.dialogue_runtime.get('report_snapshot')
            if s.pending_speaker or followup and not followup.get('done') or snapshot and not snapshot.get('done'):
                raise HTTPException(409,'진행 중인 대화나 리포트를 먼저 마쳐 주세요.')
            if not s.cards or not revision: raise HTTPException(409,'페르소나와 공개 대화를 먼저 진행하세요.')
            start=len(client.records); result=recommend(s,client)
            if len(client.records)>start: s.usage.setdefault('followup_recommendations',[]).append(client.usage(start))
            store.put(s); return result
        except (ValueError,LLMError) as exc: raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/start',response_model=Session)
    def start_lounge(id:str,options:LoungeStart):
        from .guided import GuidedConversation
        ensure_model(); acquire()
        try:
            s=get(id)
            if s.status not in ('SELECTED','FAILED','PRE') or s.transcript and any(t.phase=='group' for t in s.transcript):
                raise HTTPException(409,'이미 시작한 대화는 질문 또는 마무리를 재개하세요.')
            if s.lounge_mode and s.lounge_mode!=options.mode: raise HTTPException(409,'중단된 시작은 같은 방식으로 재개하세요.')
            start=len(client.records)
            try:
                if options.mode=='guided': GuidedConversation(client,Orchestrator(client).controller).start(s,store.put)
                else:
                    s.lounge_mode='moderated'; s.protocol_version='3'; Orchestrator(client).run(s,store.put)
                s.usage['opening']=client.usage(start); store.put(s); return s
            except (ValueError,LLMError) as exc:
                s.status='FAILED'; s.error=str(exc); s.usage.setdefault('failed_openings',[]).append(client.usage(start)); store.put(s)
                raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/finish',response_model=Session)
    def finish_lounge(id:str):
        from .guided import GuidedConversation
        ensure_model(); acquire()
        try:
            s=get(id)
            if s.lounge_mode!='guided' or s.status not in ('WAITING','CLOSING','POST','REPORT','COMPLETE'):
                raise HTTPException(409,'열린 직접 질문 대화를 먼저 진행하세요.')
            start=len(client.records)
            try: GuidedConversation(client,Orchestrator(client).controller).finish(s,store.put)
            except (ValueError,LLMError) as exc:
                s.error=str(exc); s.usage.setdefault('failed_closings',[]).append(client.usage(start)); store.put(s); raise HTTPException(502,str(exc))
            s.usage.setdefault('snapshots',[]).append(client.usage(start)); store.put(s); return s
        finally: lock.release()
    @app.post('/api/sessions/{id}/cards/{persona_id}',response_model=Session)
    def edit_card(id:str,persona_id:str,card:PersonaCard):
        ensure_model(); acquire()
        try:
            s=get(id)
            if s.status!='SELECTED': raise HTTPException(409,'Edit before the interview starts')
            old=next((c for c in s.cards if c.id==persona_id),None)
            if old is None or card.id!=persona_id: raise HTTPException(422,'Persona ID mismatch')
            card.presentation.display_name=NameEdit(display_name=card.presentation.display_name).display_name
            if any(c.id!=persona_id and c.presentation.display_name==card.presentation.display_name for c in s.cards):
                raise HTTPException(422,'참여자 이름은 서로 다르게 지정하세요.')
            if len(card.model_dump_json())>LIMITS['card_json']: raise HTTPException(422,'Card exceeds 14000 characters')
            # The selected hypothetical target cannot be changed through a card edit.
            target=Target(segment_name=old.immutable_core.identity_context.segment,why_relevant='Selected target',
                problem_exposure=old.immutable_core.identity_context.use_context,buying_role=old.immutable_core.decision_model.buying_role,
                expected_current_alternative=old.immutable_core.problem_context.current_alternative)
            audit=validate_card(card,target,[c for c in s.cards if c.id!=persona_id],s.input.evidence,client)
            if not audit.valid: raise HTTPException(422,{'message':'Card validation failed','issues':[x.model_dump() for x in audit.issues]})
            pos=s.cards.index(old); s.cards[pos]=card; s.validations[pos]=audit; ensure_session_names(s); store.put(s); return s
        except (ValueError,LLMError) as exc: raise HTTPException(422,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/ask',response_model=Session)
    def ask(id:str,q:LoungeQuestion):
        ensure_model(); acquire()
        try:
            s=get(id)
            if s.status not in ('SELECTED','FAILED','PRE','COMPLETE','WAITING'): raise HTTPException(409,'Finish or resume the current operation first')
            if not s.cards: raise HTTPException(409,'Select personas first')
            if s.status in ('FAILED','PRE') and s.lounge_mode=='moderated' and any(t.phase=='group' for t in s.transcript):
                raise HTTPException(409,'Resume the unfinished automatic interview first')
            if not q.question.strip(): raise HTTPException(422,'Question cannot be blank')
            start=len(client.records)
            try:
                from .guided import GuidedConversation
                GuidedConversation(client,Orchestrator(client).controller).ask(s,q.question,q.persona_id,store.put,q.interaction)
            except (ValueError,LLMError) as exc:
                s.error=str(exc); s.usage.setdefault('failed_followups',[]).append(client.usage(start)); store.put(s); raise
            s.usage.setdefault('followups',[]).append(client.usage(start)); store.put(s); return s
        except (ValueError,LLMError) as exc: raise HTTPException(502,str(exc))
        finally: lock.release()
    @app.post('/api/sessions/{id}/calibrate')
    def calibrate(id:str,annotation:dict):
        from eval.metrics import Annotations,metrics
        acquire()
        try:
            s=get(id)
            if s.status!='COMPLETE': raise HTTPException(409,'Complete interview first')
            try: a=Annotations.model_validate(annotation)
            except ValueError as exc: raise HTTPException(422,str(exc))
            result=metrics(a); s.calibration={'annotations':a.model_dump(),'metrics':result}
            s.calibration_revision=s.report_revision if s.report_revision is not None else sum(t.phase=='group' for t in s.transcript)
            store.put(s); return result
        finally: lock.release()
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
    @app.get('/')
    def ui(): return FileResponse(ROOT/'frontend/index.html')
    return app

app=create_app()
