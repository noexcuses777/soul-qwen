"""Recommendation type checks, bounded repair, and non-destructive legacy recovery."""
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient,LLMError
from backend.schemas import IdeaInput,Target,TargetReview,Session
from backend.services import parse_idea,generate_targets,target_label_issue

BAD_NAMES=['타깃 추천 정확도 검증','다중 페르소나 대화 시나리오','B2B 라이선스 가격 모델',
           'PoC 재사용률 지표','현장 검증 비용 절감 효과','개인 구독자 전환 경로']

class BadBatch(LLMClient):
    def __init__(self,always=False):
        super().__init__('mock');self.always=always;self.attempts=0;self.feedback=[]
    def call(self,task,payload,schema,**kw):
        result=super().call(task,payload,schema,**kw)
        if task=='targets':
            self.attempts+=1;self.feedback.append(payload.get('repair_feedback'))
            if self.always or self.attempts==1:
                for t,name in zip(result.targets,BAD_NAMES):t.segment_name=name
        return result

def test_task_batch_is_repaired_once_without_static_customer_fallback():
    llm=BadBatch();audits=[]
    ts=generate_targets(parse_idea(IdeaInput(q1='인터뷰 준비 도구',q5='IT')),[],llm,audits)
    assert llm.attempts==2 and llm.feedback[0] is None and len(llm.feedback[1])==6
    assert [r['task'] for r in llm.records]==['targets','target_review']*2
    assert [len(a.issues) for a in audits]==[6,0]
    assert [t.segment_name for t in audits[0].targets]==BAD_NAMES
    assert len(ts)==6 and not set(t.segment_name for t in ts)&set(BAD_NAMES)
    assert all(t.evidence_level==0 and t.confidence=='low' for t in ts)

def test_repeated_invalid_batch_fails_bounded_without_saving_empty_session(tmp_path):
    llm=BadBatch(always=True);api=TestClient(create_app(str(tmp_path/'bad.db'),llm))
    r=api.post('/api/sessions',json={'q1':'idea','q5':'IT'})
    assert r.status_code==502 and '다시 추천' in r.json()['detail']
    assert llm.attempts==2 and api.get('/api/latest').json() is None

@pytest.mark.parametrize('name',BAD_NAMES+['UNKNOWN',' '])
def test_bare_task_label_rejected(name):
    assert target_label_issue(Target(segment_name=name,why_relevant='관련 있음'))

@pytest.mark.parametrize('name',[
    '고객 인터뷰를 준비하는 예비창업자','B2B 기관 라이선스 구매자 (액셀러레이터/창업지원단)',
    'B2B 라이선스 가격 모델을 비교하는 창업지원 담당자','재사용률 지표를 살펴보는 프로그램 운영자',
    '온라인 주문을 받는 동네 카페','경작 기록을 관리하는 소규모 농가','통근 중 자전거를 이용하는 시민'])
def test_valid_participant_labels_are_not_a_domain_allowlist(name):
    assert target_label_issue(Target(segment_name=name,why_relevant='관련 있음')) is None

@pytest.mark.parametrize('broken',['missing','duplicate','unrelated','not_person'])
def test_semantic_reviewer_must_cover_all_and_pass_type_and_fit(broken):
    class Critic(LLMClient):
        def call(self,task,payload,schema,**kw):
            result=super().call(task,payload,schema,**kw)
            if task=='target_review':
                if broken=='missing':result.items.pop()
                if broken=='duplicate':result.items[-1].index=0
                if broken=='unrelated':result.items[0].fits_idea=False
                if broken=='not_person':result.items[0].is_participant=False
            return result
    llm=Critic('mock')
    with pytest.raises(ValueError,match='추천'):generate_targets(parse_idea(IdeaInput(q1='idea',q5='IT')),[],llm)
    assert len(llm.records)==4

def api_session(tmp_path):
    llm=LLMClient('mock');api=TestClient(create_app(str(tmp_path/'targets.db'),llm))
    s=api.post('/api/sessions',json={'q1':'idea','q5':'IT'}).json()
    return api,llm,s

def test_unchanged_approved_selection_reuses_review_and_exact_segment(tmp_path):
    api,llm,s=api_session(tmp_path);start=len(llm.records)
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'custom_targets':[s['targets'][0]]})
    assert r.status_code==200,r.text
    assert not any(x['task']=='target_review' for x in llm.records[start:])
    assert r.json()['cards'][0]['immutable_core']['identity_context']['segment']==s['targets'][0]['segment_name']

def test_new_user_target_reviewed_before_build_and_never_silently_rewritten(tmp_path):
    api,llm,s=api_session(tmp_path);start=len(llm.records)
    label='온라인 주문을 받는 동네 카페'
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'custom_targets':[{'segment_name':label,'why_relevant':'주문 준비 상황'}]})
    assert r.status_code==200,r.text
    assert llm.records[start]['task']=='target_review'
    assert r.json()['cards'][0]['immutable_core']['identity_context']['segment']==label
    assert r.json()['target_audits'][-1]['stage']=='selection'

def test_topic_custom_selection_fails_before_any_build_and_keeps_session(tmp_path):
    api,llm,s=api_session(tmp_path);before=api.get(f'/api/sessions/{s["id"]}').json();start=len(llm.records)
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'custom_targets':[{'segment_name':BAD_NAMES[0],'why_relevant':'과제'}]})
    assert r.status_code==422 and '어떤 이용자인지' in r.json()['detail']
    assert len(llm.records)==start and api.get(f'/api/sessions/{s["id"]}').json()==before

def test_duplicate_custom_participants_rejected_before_model(tmp_path):
    api,llm,s=api_session(tmp_path);start=len(llm.records)
    r=api.post(f'/api/sessions/{s["id"]}/select',json={'custom_targets':[s['targets'][0]]*2})
    assert r.status_code==422 and '중복' in r.json()['detail'] and len(llm.records)==start

def test_legacy_bad_targets_stay_readable_and_can_be_explicitly_replaced(tmp_path):
    api,llm,s=api_session(tmp_path);old=api.app.state.store.get(s['id']);old.target_audits=[]
    for t,name in zip(old.targets,BAD_NAMES):t.segment_name=name
    # Emulate an old payload without the additive audit field.
    old=Session.model_validate(old.model_dump(exclude={'target_audits'}));api.app.state.store.put(old)
    assert api.get(f'/api/sessions/{s["id"]}').json()['targets'][0]['segment_name']==BAD_NAMES[0]
    r=api.post(f'/api/sessions/{s["id"]}/targets/recommend',json={});assert r.status_code==200,r.text
    changed=r.json();assert changed['id']==s['id'] and changed['input']==s['input'] and not changed['cards']
    assert [t['segment_name'] for t in changed['target_audits'][0]['targets']]==BAD_NAMES
    assert changed['target_audits'][0]['stage']=='replaced' and len(changed['target_audits'])==2
    assert changed['targets'][0]['segment_name']!=BAD_NAMES[0]

def test_regeneration_failure_keeps_previous_recommendations(tmp_path):
    api,llm,s=api_session(tmp_path);before=api.get(f'/api/sessions/{s["id"]}').json()
    def fail(*args,**kwargs):raise LLMError('transport interrupted')
    llm.call=fail
    assert api.post(f'/api/sessions/{s["id"]}/targets/recommend',json={}).status_code==502
    assert api.get(f'/api/sessions/{s["id"]}').json()==before

def test_regeneration_cannot_replace_selected_personas_or_chat(tmp_path):
    api,llm,s=api_session(tmp_path)
    api.post(f'/api/sessions/{s["id"]}/select',json={'target_ids':['t1']}).raise_for_status()
    before=api.get(f'/api/sessions/{s["id"]}').json();start=len(llm.records)
    assert api.post(f'/api/sessions/{s["id"]}/targets/recommend',json={}).status_code==409
    assert len(llm.records)==start and api.get(f'/api/sessions/{s["id"]}').json()==before

def test_ui_wording_keeps_target_and_persona_stages_distinct(tmp_path):
    api,_,_=api_session(tmp_path);html=api.get('/').text;js=api.get('/assets/app.js').text
    assert '타깃 추천받기 →' in html and '타깃 가설 추천받기' not in html
    assert '타깃 다시 추천받기' in html and '어떤 이용자인가요?' in js
    assert '페르소나 생성·검사' in html and '프로필' in js
