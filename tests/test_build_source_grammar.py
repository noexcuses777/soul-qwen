"""Inspect the actual OpenAI request grammar, without pretending to run Qwen."""
import json
import httpx,pytest
from backend.llm import LLMClient
from backend.mock import fixture
from backend.schemas import PersonaCard

@pytest.mark.parametrize('evidence',[[],[{'source_id':'market','level':1,'text':'시장 자료'}],
    [{'source_id':'interview','level':3,'text':'허가된 인터뷰'}, {'source_id':'market','level':1,'text':'시장 자료'}]])
def test_build_references_only_supplied_sources_and_timeline_requires_l2(evidence):
    requests=[]
    payload={'target':{'segment_name':'고객 인터뷰를 준비하는 창업자','problem_exposure':'인터뷰 준비 상황'},
             'persona_id':'p1','evidence':evidence}
    def handle(req):
        if req.url.path=='/props':return httpx.Response(200,json={'default_generation_settings':{'n_ctx':8192}})
        if req.url.path=='/apply-template':return httpx.Response(404)
        if req.url.path=='/tokenize':return httpx.Response(200,json={'tokens':[1]*1000})
        body=json.loads(req.content);requests.append(body)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(fixture('build',payload))}}]})
    LLMClient('qwen',transport=httpx.MockTransport(handle)).call('build',payload,PersonaCard,max_tokens=1100)
    grammar=requests[-1]['response_format']['json_schema']['schema'];defs=grammar['$defs']
    refs=defs['ReasoningRule']['properties']['evidence_ids'];source_ids={e['source_id'] for e in evidence}
    if source_ids:
        assert set(refs['items']['enum'])==source_ids
        assert set(defs['Anchor']['properties']['source_id']['enum'])==source_ids
    else:
        assert refs['maxItems']==0 and defs['Core']['properties']['evidence_anchors']['maxItems']==0
    customer_ids={e['source_id'] for e in evidence if e['level']>=2}
    if customer_ids:assert set(defs['TimelineEvent']['properties']['source_id']['enum'])==customer_ids
    else:assert defs['Core']['properties']['timeline']['maxItems']==0
