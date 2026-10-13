import copy, json, os, threading, time
from urllib.parse import urlparse
import httpx
from pydantic import ValidationError
from .prompts import COMMON,PROMPTS

class LLMError(RuntimeError): pass

def output_contract(schema):
    """Expose field layout to the model as well as using server grammar constraints."""
    raw=schema.model_json_schema();defs=raw.get('$defs',{})
    def shape(node):
        if '$ref' in node: return shape(defs[node['$ref'].split('/')[-1]])
        if 'properties' in node:
            # Optional newly extended fields are accepted by grammar, without a huge repeated skeleton.
            extra={'occupation','life_stage','region','technical_literacy','domain_experience','workaround',
                   'past_failed_attempts','risk_sensitivity','decision_authority','must_have','rejection_conditions',
                   'functional_goal','emotional_goal','social_goal','motivation','stable_profile',
                   'verbosity','emotional_expression','technical_vocabulary','question_style','agreement_threshold','uncertainty_expression',
                   'presentation','timeline','quality_flags','generated_content'}
            return {k:shape(v) for k,v in node['properties'].items() if k not in extra}
        if node.get('type')=='array': return [shape(node['items'])]
        if 'enum' in node: return '|'.join(map(str,node['enum']))
        if 'const' in node: return node['const']
        if 'minimum' in node or 'maximum' in node:
            return f"{node.get('type','number')} [{node.get('minimum','')}..{node.get('maximum','')}]"
        if 'anyOf' in node: return shape(node['anyOf'][0])
        if 'additionalProperties' in node and isinstance(node['additionalProperties'],dict): return {'<key>':shape(node['additionalProperties'])}
        return node.get('type','value')
    return shape(raw)

def compact(value):
    """Missing optional facts mean UNKNOWN. Never discard nonempty constraints or anchors."""
    if isinstance(value,dict):
        return {k:compact(v) for k,v in value.items() if v not in ('UNKNOWN','',None) and v!=[] and v!={}}
    if isinstance(value,list): return [compact(v) for v in value]
    return value

def shrink_history(payload):
    # Operates on a copy. Full source transcript remains persisted and owned by its persona.
    buffers=[payload.get(k) for k in ('own','group') if isinstance(payload.get(k),dict)]
    choices=[b for b in buffers if len(b.get('recent',[]))>1]
    if choices:
        b=max(choices,key=lambda x:len(json.dumps(x,ensure_ascii=False)))
        old=b['recent'].pop(0)
        line=f"[{old.get('id')} {old.get('persona_id')} {old.get('phase')}] {old.get('content','')[:160]} | {old.get('reason','')[:80]}"
        b['older_summary']=(b.get('older_summary','')+'\n'+line)[-650:]
        payload['context_note']='Older utterances are excerpts, not full observations. Missing detail is unknown.'
        return True
    for b in buffers:
        if len(b.get('older_summary',''))>180:
            lines=b['older_summary'].splitlines()
            b['older_summary']=lines[-1][:180] if lines else ''; return True
        for turn in b.get('recent',[]):
            if len(turn.get('content',''))>160:
                turn['content']=turn['content'][:max(160,len(turn['content'])//2)]
                turn['excerpt_only']=True; payload['context_note']='Recent content is an excerpt. Preserve visible conditions; omitted detail is unknown.'
                return True
    for source in payload.get('evidence',[]):
        for span in source.get('excerpts',[]):
            if len(span.get('text',''))>150:
                span['text']=span['text'][:max(150,len(span['text'])//2)];source['excerpt_only']=True;return True
        if len(source.get('excerpts',[]))>1:
            source['excerpts']=source['excerpts'][:1];source['excerpt_only']=True;return True
    turns=payload.get('transcript',[])
    if len(turns)>12 and isinstance(turns[0],str):
        for i,t in enumerate(turns):
            parts=t.split('|',4)
            if len(parts)>=3 and parts[2] not in ('pre','post') and any(x.split('|',4)[1:3]==parts[1:3] for x in turns[i+1:]):
                turns.pop(i); payload['omitted_utterance_count']=payload.get('omitted_utterance_count',0)+1
                payload['context_note']='Report uses private baseline/latest opinion and recent public conditions; inspect full transcript.'
                return True
    return False

class LLMClient:
    """One sequential shared model. Explicit mock; never silently fallback on failure."""
    def __init__(self,mode=None,base_url=None,transport=None,context_size=None):
        self.mode=mode or os.getenv('LLM_MODE','mock')
        if self.mode not in ('mock','qwen'): raise ValueError('LLM_MODE must be mock or qwen')
        self.base_url=(base_url or os.getenv('LLM_BASE_URL','http://127.0.0.1:8080/v1')).rstrip('/')
        if urlparse(self.base_url).hostname not in ('localhost','127.0.0.1','::1'): raise ValueError('local LLM URL required')
        self.model=os.getenv('LLM_MODEL','persona-qwen')
        self.context_size=context_size or int(os.getenv('CONTEXT_SIZE','8192'))
        self.http=httpx.Client(timeout=float(os.getenv('LLM_TIMEOUT','180')),transport=transport,trust_env=False)
        self.lock=threading.Lock(); self.records=[]; self.server_info={}; self.info_at=0

    def server_context(self):
        if time.monotonic()-self.info_at>30:
            try:
                r=self.http.get(self.base_url.removesuffix('/v1')+'/props'); r.raise_for_status()
                raw=r.json(); self.server_info={
                    'context_size':raw.get('default_generation_settings',{}).get('n_ctx'),
                    'model_file':os.path.basename(raw.get('model_path','').replace('\\','/')),
                    'slots':raw.get('total_slots',1)}
            except (httpx.HTTPError,ValueError,TypeError): pass
            self.info_at=time.monotonic()
        ctx=self.server_info.get('context_size')
        return min(self.context_size,int(ctx)) if ctx else self.context_size

    def health(self):
        if self.mode=='mock':
            return {'connected':True,'mode':'mock','model':'synthetic-fixtures'}
        try:
            health=self.http.get(self.base_url.removesuffix('/v1')+'/health')
            models=self.http.get(self.base_url+'/models')
            health.raise_for_status(); models.raise_for_status()
            ids=[row.get('id') for row in models.json().get('data',[])]
            context=self.server_context()
            return {'connected':True,'mode':'qwen','model':self.model,'server':health.json(),'available_models':ids,
                    **self.server_info,'effective_context_size':context}
        except (httpx.HTTPError,ValueError,TypeError) as exc:
            return {'connected':False,'mode':'qwen','model':self.model,'error':type(exc).__name__}

    def call(self,task,payload,schema,max_tokens=700,seed=42,repair=True):
        with self.lock:
            return self._call(task,payload,schema,max_tokens,seed,repair)

    def _call(self,task,payload,schema,max_tokens,seed,repair):
        start=time.perf_counter()
        if self.mode=='mock':
            from .mock import fixture
            result=schema.model_validate(fixture(task,payload))
            self.records.append({'task':task,'prompt_tokens':None,'completion_tokens':None,'mock':True,'latency_s':time.perf_counter()-start,'max_tokens':max_tokens})
            return result
        payload=compact(copy.deepcopy(payload)); packed=0; recovery=''
        limit=self.server_context()
        grammar=schema.model_json_schema()
        if task=='build':
            core=grammar['$defs']['Core']
            core['required']=list(dict.fromkeys(core.get('required',[])+['reasoning_rules']))
            core['properties']['reasoning_rules'].update(minItems=1,maxItems=2)
            target=payload.get('target',{})
            bases=['identity_context.segment']
            for key,paths in [('buying_role',['identity_context.role','decision_model.buying_role']),
                              ('problem_exposure',['identity_context.use_context']),
                              ('expected_current_alternative',['problem_context.current_alternative'])]:
                if target.get(key) not in (None,'', 'UNKNOWN'): bases.extend(paths)
            grammar['$defs']['ReasoningRule']['properties']['basis_fields']['items']={'type':'string','enum':bases}
        if task=='questions':
            ids=[c['id'] for c in payload.get('participants',[])]
            grammar['$defs']['QuestionSuggestion']['properties']['persona_id']={'anyOf':[{'type':'string','enum':ids},{'type':'null'}]} if ids else {'type':'null'}
        def references(node,allowed):
            node.update({'type':'array','items':{'type':'string','enum':sorted(allowed)},'maxItems':3}) if allowed else node.update({'type':'array','items':{'type':'string'},'maxItems':0})
        if task=='followup_plan':
            refs={t['id'] for t in payload.get('latest_public',[])}
            references(grammar['$defs']['FollowupCandidate']['properties']['source_utterance_ids'],refs)
        if task=='followup_review':
            grammar['$defs']['FollowupJudgment']['properties']['index']={'type':'integer','enum':[c['index'] for c in payload.get('candidates',[])]}
        source_ids={s['source_id'] for s in payload.get('evidence',[]) if 'source_id' in s}
        if task=='targets': references(grammar['$defs']['Target']['properties']['evidence_ids'],source_ids)
        if task=='build':
            references(grammar['$defs']['ReasoningRule']['properties']['evidence_ids'],source_ids)
            anchors=grammar['$defs']['Core']['properties']['evidence_anchors']
            if source_ids:
                grammar['$defs']['Anchor']['properties']['source_id']={'type':'string','enum':sorted(source_ids)}
            else: anchors.update(maxItems=0)
            timeline_ids={s['source_id'] for s in payload.get('evidence',[]) if s.get('level',0)>=2}
            if timeline_ids:
                grammar['$defs']['TimelineEvent']['properties']['source_id']={'type':'string','enum':sorted(timeline_ids)}
            else: grammar['$defs']['Core']['properties']['timeline'].update(maxItems=0)
        if task in ('agent','interact','chat'):
            core=payload.get('card',{}).get('immutable_core',{})
            references(grammar['properties']['evidence_ids'],{a['source_id'] for a in core.get('evidence_anchors',[])})
            references(grammar['properties']['reasoning_rule_ids'],{r['id'] for r in core.get('reasoning_rules',[])})
            if core.get('reasoning_rules'):grammar['required']=list(dict.fromkeys(grammar.get('required',[])+['reasoning_rule_ids']))
            grammar['properties']['quality_flags'].update(maxItems=0)
            if task in ('interact','chat'):
                ids=payload.get('participants',[])
                grammar['properties']['addressed_to']={'anyOf':[{'type':'string','enum':ids},{'type':'null'}]} if ids else {'type':'null'}
            if task=='chat':
                # Emit the persona's own perspective first. This primes generation before peer text
                # can become the speaker's claimed role/alternative; it is not a faithfulness score.
                basis={'type':'object','properties':{
                    'role':{'type':'string','const':core.get('decision_model',{}).get('buying_role','UNKNOWN')},
                    'expected_alternative':{'type':'string','const':core.get('problem_context',{}).get('current_alternative','UNKNOWN')}},
                    'required':['role','expected_alternative'],'additionalProperties':False}
                grammar['properties']={'own_basis':basis,**{k:v for k,v in grammar['properties'].items() if k!='own_basis'}}
                grammar['required']=list(dict.fromkeys(['own_basis']+grammar.get('required',[])+['followup_kind','reason','stance','unresolved_issues','reasoning_rule_ids']))
        if task=='report':
            refs={t.split('|')[0] if isinstance(t,str) else t['id'] for t in payload.get('transcript',[])}
            references(grammar['$defs']['Insight']['properties']['utterance_ids'],refs)
            if refs:
                grammar['$defs']['Insight']['properties']['utterance_ids']['minItems']=1
                grammar['$defs']['Insight']['required']=list(dict.fromkeys(grammar['$defs']['Insight'].get('required',[])+['utterance_ids']))
            references(grammar['$defs']['Insight']['properties']['evidence_ids'],{e['id'] for e in payload.get('sources',[])})
        layout=output_contract(schema)
        if task=='chat': layout={'own_basis':{'role':'EXACT own role','expected_alternative':'EXACT own expected alternative'},**{k:v for k,v in layout.items() if k!='own_basis'}}
        system=COMMON+'\n'+PROMPTS[task]+'\nMissing optional facts mean UNKNOWN/default, not evidence. Omit optional unknown fields to save tokens.\nOutput field layout: '+json.dumps(layout,ensure_ascii=False,separators=(',',':'))
        def messages_for():
            return [{'role':'system','content':system+recovery},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]
        def count(messages):
            rendered='\n'.join(m['content'] for m in messages); margin=128
            # Count the actual chat template when supported, otherwise reserve special-token overhead.
            template=self.http.post(self.base_url.removesuffix('/v1')+'/apply-template',json={'messages':messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}})
            if template.is_success and isinstance(template.json().get('prompt'),str):
                rendered=template.json()['prompt']; margin=32
            tok=self.http.post(self.base_url.removesuffix('/v1')+'/tokenize',json={'content':rendered,'add_special':True})
            return len(tok.json()['tokens'])+margin if tok.is_success else len(rendered.encode('utf-8'))+200
        for attempt in range(2 if repair else 1):
            try:
                messages=messages_for(); estimated=count(messages)
                while estimated+max_tokens>limit and shrink_history(payload):
                    packed+=1; messages=messages_for(); estimated=count(messages)
                if estimated+max_tokens>limit:
                    raise LLMError(f'Context: 필요한 문맥 {estimated}+출력 {max_tokens} tokens, 서버 한도 {limit}. 근거 자료를 관련 발췌로 줄이거나 통합 실행기를 -Context 8192로 다시 시작하세요.')
                # Reference grammar must match the actual packed prompt, not discarded history.
                if task in ('agent','interact','chat'):
                    visible={t['id'] for t in payload.get('group',{}).get('recent',[])}
                    parent=payload.get('required_parent',{})
                    if parent.get('id'): visible.add(parent['id'])
                    grammar['properties']['reply_to']={'anyOf':[{'type':'string','enum':sorted(visible)},{'type':'null'}]} if visible else {'type':'null'}
                if task=='report':
                    references(grammar['$defs']['Insight']['properties']['utterance_ids'],{t.split('|')[0] if isinstance(t,str) else t['id'] for t in payload.get('transcript',[])})
                body={'model':self.model,'messages':messages,'temperature':.3,'seed':seed,'max_tokens':max_tokens,
                      'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':True,
                      'response_format':{'type':'json_schema','json_schema':{'name':schema.__name__,'strict':True,'schema':grammar}}}
                # Retry a transient connection/503 once. Never switch to mock or duplicate a saved turn.
                for retry in range(2 if repair else 1):
                    try:
                        response=self.http.post(self.base_url+'/chat/completions',json=body)
                        if response.status_code in (502,503,504) and retry==0 and repair: time.sleep(.3); continue
                        response.raise_for_status(); break
                    except (httpx.ConnectError,httpx.ReadTimeout):
                        if retry or not repair: raise
                        time.sleep(.3)
                response.raise_for_status(); raw=response.json()
                self.records.append({'task':task,**raw.get('usage',{}),'latency_s':time.perf_counter()-start,'max_tokens':max_tokens,'attempt':attempt,
                                     'context_compactions':packed,'context_limit':limit,'estimated_prompt_tokens':estimated,'timings':raw.get('timings',{})})
                choice=raw['choices'][0]
                if choice.get('finish_reason')=='length': raise ValueError('truncated JSON output')
                return schema.model_validate_json(choice['message']['content'])
            except (ValidationError,ValueError,KeyError,TypeError) as exc:
                if attempt+1 >= (2 if repair else 1):
                    detail='; '.join(str(x['loc'])+': '+x['msg'] for x in exc.errors(include_input=False)[:3]) if isinstance(exc,ValidationError) else str(exc)
                    raise LLMError(f'{task}: invalid JSON/schema after bounded attempts ({detail})') from exc
                detail='; '.join(str(x['loc'])+': '+x['msg'] for x in exc.errors(include_input=False)[:4]) if isinstance(exc,ValidationError) else str(exc)
                recovery='\nPrevious output invalid: '+detail+'. Correct these fields. Return short complete JSON matching schema, no fabricated facts.'
                if 'truncated' in str(exc): max_tokens=min(max_tokens*2,limit//2)
            except httpx.HTTPError as exc:
                raise LLMError(f'{task}: local model transport failed ({type(exc).__name__})') from exc

    def usage(self,start=0):
        rows=self.records[start:]
        measured=self.mode=='qwen' and all('prompt_tokens'in r and 'completion_tokens'in r for r in rows)
        prompt=sum(r['prompt_tokens'] for r in rows) if measured else None
        completion=sum(r['completion_tokens'] for r in rows) if measured else None
        return {'calls':len(rows),'prompt_tokens':prompt,
                'completion_tokens':completion,
                'estimated_token_cost_usd':(prompt+completion)*float(os.getenv('TOKEN_PRICE_PER_MILLION','0'))/1_000_000 if measured else None,
                'cost_basis':'configured accounting price per total token; excludes electricity/hardware',
                'latency_s':sum(r['latency_s'] for r in rows),'records':rows,'mode':self.mode}
