import json
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.llm import LLMClient
from backend.schemas import PersonaCard

class Recording(LLMClient):
    def __init__(self):
        super().__init__('mock')
        self.inputs=[]
    def call(self, task, data, *args, **kwargs):
        self.inputs.append((task,json.dumps(data,ensure_ascii=False)))
        return super().call(task,data,*args,**kwargs)

def fresh(tmp_path, name):
    llm=Recording()
    client=TestClient(create_app(str(tmp_path/name),llm))
    session=client.post('/api/sessions',json={'q1':'합성 예약 도구','q5':'IT'}).json()
    return client,session,llm

def test_selected_names_persist_without_changing_model_input_or_core(tmp_path):
    client,session,llm=fresh(tmp_path,'named.db')
    legacy,baseline,old=fresh(tmp_path,'baseline.db')
    ids=['t3','t1']
    chosen=client.post(f'/api/sessions/{session["id"]}/select',json={'target_ids':ids,'display_names':{'t3':'윤서아','t1':'강서준'}})
    unchanged=legacy.post(f'/api/sessions/{baseline["id"]}/select',json={'target_ids':ids})
    assert chosen.status_code==unchanged.status_code==200
    value=chosen.json()
    assert value['selected_target_ids']==ids
    assert [c['presentation']['display_name'] for c in value['cards']]==['윤서아','강서준']
    assert [c['immutable_core'] for c in value['cards']]==[c['immutable_core'] for c in unchanged.json()['cards']]
    assert llm.inputs==old.inputs
    assert client.get(f'/api/sessions/{session["id"]}').json()['selected_target_ids']==ids
    assert set(PersonaCard.model_json_schema()['$defs']['Presentation']['properties'])=={'display_name','fictional'}

@pytest.mark.parametrize('names',[{'t1':''},{'t1':'하늘\n'+'다른 줄'}, {'t1':'이'*25}, {'t2':'하늘'}, {'t1':'김하늘','t2':' 김하늘 '}, {'t1':'김하늘','t9':'이다온'}])
def test_invalid_name_metadata_rejected_before_model_call(tmp_path,names):
    client,session,llm=fresh(tmp_path,'bad.db')
    ids=['t1','t2'] if len(names)>1 else ['t1']
    count=len(llm.inputs)
    assert client.post(f'/api/sessions/{session["id"]}/select',json={'target_ids':ids,'display_names':names}).status_code==422
    assert len(llm.inputs)==count
    assert client.get(f'/api/sessions/{session["id"]}').json()['cards']==[]

def test_failed_core_edit_does_not_partially_rename(tmp_path):
    client,session,llm=fresh(tmp_path,'atomic.db')
    selected=client.post(f'/api/sessions/{session["id"]}/select',json={'target_ids':['t1','t2']}).json()
    card=selected['cards'][0]
    original_name=card['presentation']['display_name']
    card['presentation']['display_name']='수정한 이름'
    card['immutable_core']['identity_context']['age']='35'
    assert client.post(f'/api/sessions/{session["id"]}/cards/p1',json=card).status_code==422
    saved=client.get(f'/api/sessions/{session["id"]}').json()['cards'][0]
    assert saved['presentation']['display_name']==original_name
    assert saved['immutable_core']['identity_context']['age']=='UNKNOWN'
    card=saved
    card['presentation']['display_name']=selected['cards'][1]['presentation']['display_name']
    count=len(llm.inputs)
    assert client.post(f'/api/sessions/{session["id"]}/cards/p1',json=card).status_code==422
    assert len(llm.inputs)==count


def test_recommendation_aliases_are_random_unique_and_persisted(tmp_path):
    client,first,llm=fresh(tmp_path,'random.db')
    second=client.post('/api/sessions',json={'q1':'합성 예약 도구','q5':'IT'}).json()
    names=first['target_display_names']
    assert set(names)=={target['id'] for target in first['targets']}
    assert len(set(names.values()))==len(first['targets'])
    assert names!=second['target_display_names']
    assert all(2<=len(name)<=4 for name in names.values())
    assert client.get(f'/api/sessions/{first["id"]}').json()['target_display_names']==names
    assert client.app.state.store.get(first['id']).target_display_names==names
    # Cosmetic labels are neither target properties nor factual/semantic model inputs.
    assert all('target_display_names' not in payload for _,payload in llm.inputs)
    assert all('display_name' not in target for target in first['targets'])


def test_selected_aliases_match_preview_and_custom_names_survive_reload(tmp_path):
    client,session,_=fresh(tmp_path,'association.db')
    base=f'/api/sessions/{session["id"]}'
    selected=client.post(base+'/select',json={'target_ids':['t5','t2']}).json()
    assert [card['presentation']['display_name'] for card in selected['cards']]==[
        session['target_display_names'][target_id] for target_id in ['t5','t2']]
    renamed=client.post(base+'/names/p1',json={'display_name':'직접 지정한 이름'}).json()
    assert renamed['target_display_names']['t5']=='직접 지정한 이름'
    assert client.get(base).json()['cards'][0]['presentation']['display_name']=='직접 지정한 이름'
    assert client.get(base).json()['target_display_names']==renamed['target_display_names']


def test_recommend_again_refreshes_names_without_reusing_previous_set(tmp_path):
    client,session,_=fresh(tmp_path,'regenerate.db')
    refreshed=client.post(f'/api/sessions/{session["id"]}/targets/recommend',json={}).json()
    assert not set(session['target_display_names'].values()) & set(refreshed['target_display_names'].values())
    assert client.get(f'/api/sessions/{session["id"]}').json()['target_display_names']==refreshed['target_display_names']


def test_legacy_names_are_stable_and_preserved_without_rewriting_session_on_read(tmp_path):
    client,session,_=fresh(tmp_path,'legacy.db')
    base=f'/api/sessions/{session["id"]}'
    selected=client.post(base+'/select',json={'target_ids':['t1','t2'],'display_names':{'t1':'기존 이름','t2':'사용자 이름'}}).json()
    legacy=client.app.state.store.get(session['id'])
    legacy.target_display_names={}
    client.app.state.store.put(legacy)
    first=client.get(base).json()
    second=client.get(base).json()
    assert first['target_display_names']==second['target_display_names']
    assert [card['presentation']['display_name'] for card in first['cards']]==['기존 이름','사용자 이름']
    assert first['target_display_names']['t1']=='기존 이름'
    assert client.app.state.store.get(session['id']).target_display_names=={}
