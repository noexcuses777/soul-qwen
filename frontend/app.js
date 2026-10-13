let session=null,busy=false,limits={},polling=null,pollGeneration=0,pollInFlight=false,writeVersion=0;
let lastLogSignature='',lastReportSignature='',scrollChatOnNextRender=false,optimisticMessage=null;
const $=id=>document.getElementById(id),chars=s=>[...s].length;
const questions=[['q1','Q1. 나의 아이디어를 한 줄로 소개해주세요.'],['q2','Q2. 아이디어를 떠올린 배경 이야기를 들려주세요.'],[null,'Q3. 어떤 아이디어인가요?'],['q3_1','Q3-1. 기존 제품 및 서비스 대비 차별점과 어떤 문제를 해결할 수 있나요?'],['q3_2','Q3-2. 어떻게 수익을 창출할 계획인가요?'],[null,'Q4. 어떻게 실현하고 싶으신가요?'],['q4_1','Q4-1. 아이디어를 어떻게 사업화하실 계획이신가요?']];
function counter(input,max){const s=document.createElement('small');s.className='counter';input.after(s);input.dataset.limit=max;const update=()=>{const n=chars(input.value);s.textContent=`${n.toLocaleString()} / ${max.toLocaleString()}자`;s.classList.toggle('over',n>max);input.setCustomValidity(n>max?`${max}자 한도를 초과했습니다.`:'');};input.addEventListener('input',update);update();}
function updateCounters(){document.querySelectorAll('[data-limit]').forEach(x=>x.dispatchEvent(new Event('input')));}
async function api(path,data){const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)}),j=await r.json();if(!r.ok){let m=j.detail;if(Array.isArray(m))m=m.map(e=>`${e.loc?.slice(1).join('.')}: ${e.msg}`).join('\n');else if(typeof m!=='string')m=JSON.stringify(m);throw Error(m);}return j;}
function save(s,fromPoll=false){if(!fromPoll)writeVersion++;session=s;localStorage.setItem('persona-session',s.id);}
const aliases=['김하늘','이다온','박시온'];
function personaName(c){return c?.presentation?.display_name||aliases[session?.cards?.indexOf(c)]||c?.id||'참여자';}
function segmentText(c){const segment=c?.immutable_core?.identity_context?.segment;return !segment||segment==='UNKNOWN'?'타깃 예시 미확인':segment;}
function identityLabel(c){return `${personaName(c)} · ${segmentText(c)}`;}
function displayText(text){
  // Hide internal rule references only in reader-facing prose; the stored response and audit details stay intact.
  const reference='(?:p[1-3]\\s*:\\s*)?r[12]',list=reference+'(?:\\s*[,，/·]\\s*'+reference+')*';
  const particles='(?:은|는|을|를|의|에|에서|으로|로|과|와|이|가|도|만|부터|처럼|까지|에게|이라는|이라고|이라면|입니다|이며|이고)';
  const prose=text
    .replace(new RegExp('\\(\\s*'+list+'\\s*\\)|\\[\\s*'+list+'\\s*\\]|（\\s*'+list+'\\s*）','g'),'')
    .replace(new RegExp('`\\s*'+reference+'\\s*`','g'),'판단 기준')
    .replace(new RegExp('(?<![\\p{L}\\p{N}_:])'+reference+'(?=$|[^\\p{L}\\p{N}_]|'+particles+'(?=$|[^\\p{L}\\p{N}_]))','gu'),'판단 기준');
  // Fail open if the optional formatter is unavailable; chat must still render.
  return typeof PersonaKoreanText==='undefined'?prose:PersonaKoreanText.normalize(prose);
}
function pendingQuestion(){const q=session?.dialogue_runtime?.followup;return q&&!q.done?q:null;}
function saveDraft(){if(session)localStorage.setItem(`persona-draft:${session.id}`,$('ask-question').value);}
function restoreDraft(){if(!session)return;$('ask-question').value=localStorage.getItem(`persona-draft:${session.id}`)||'';updateCounters();}
function syncButtons(){document.querySelectorAll('button').forEach(b=>b.disabled=busy&&b.dataset.readonly!=='true');document.querySelectorAll('[data-card-edit]').forEach(b=>b.disabled=busy||session?.status!=='SELECTED');updateRun();}
function updateRun(){
  if(!session)return;
  const selected=!!session.cards.length,legacyResume=session.lounge_mode==='moderated'&&['FAILED','PRE','GROUP','POST','REPORT'].includes(session.status);
  $('target-choice').hidden=selected;$('target-heading').textContent=selected?'02 선택한 페르소나':'02 대화할 이용자 유형을 선택하세요';
  $('recommend-targets').disabled=busy||session.status!=='CREATED';
  $('legacy-resume').hidden=!legacyResume;$('chat-composer').hidden=!selected;
  const closing=session.lounge_mode==='guided'&&['CLOSING','POST','REPORT'].includes(session.status);
  const ready=['SELECTED','WAITING','COMPLETE'].includes(session.status)||(['FAILED','PRE'].includes(session.status)&&session.lounge_mode!=='moderated'&&!session.transcript.some(t=>t.phase==='group'));
  $('ask').disabled=busy||!ready||!!pendingQuestion();$('ask').textContent=busy&&optimisticMessage?'응답 생성 중…':'보내기 ↑';
  $('retry-question').hidden=!pendingQuestion();$('retry-question').disabled=busy;
  $('finish').hidden=session.lounge_mode!=='guided'||!['WAITING','COMPLETE','CLOSING','POST','REPORT'].includes(session.status);
  $('finish').textContent=closing?'리포트 생성 이어받기':session.report?'리포트 업데이트':'리포트 만들기';
  $('finish').disabled=busy||!!pendingQuestion()||(!closing&&!session.transcript.some(t=>t.phase==='group'))||!!(session.report&&!session.report_stale&&session.status==='COMPLETE');
  $('finish').title=session.report&&!session.report_stale?'최신 대화가 반영된 리포트입니다.':'대화를 정리한 뒤에도 이 채팅창에서 계속 질문할 수 있습니다.';
  $('get-suggestions').hidden=!!session.suggestions?.length;$('get-suggestions').disabled=busy;
  $('ask-question').setAttribute('aria-describedby','chat-live');
}
function openProfile(c){
  const root=$('profile-body');root.replaceChildren();const h=document.createElement('h2');h.textContent=personaName(c)+' · 가상 이름';root.append(h);
  const label=document.createElement('label');label.textContent='표시 이름 (24자 이내)';const input=document.createElement('input');input.value=personaName(c);input.maxLength=24;label.append(input);
  const rename=document.createElement('button');rename.textContent='이름 저장';rename.disabled=busy;rename.onclick=()=>action('이름을 저장합니다…',async()=>{save(await api(`/api/sessions/${session.id}/names/${c.id}`,{display_name:input.value}));$('profile').close();renderCards();renderInterview();});root.append(label,rename);
  const core=c.immutable_core;
  for(const [title,lines] of [
    ['Who · 어떤 상황의 참여자인가',[segmentText(c),`상황: ${core.identity_context.use_context}`]],
    ['What · 문제와 결정 조건',[`예상 대안: ${core.problem_context.current_alternative}`,`도입 장벽: ${core.decision_model.adoption_barrier}`,`전환 비용: ${core.decision_model.switching_cost}`,`예산 제약: ${core.decision_model.budget_constraint}`]],
    ['How · 어떻게 말하는가',[core.interaction_style.speech,core.interaction_style.directness,core.interaction_style.agreement_threshold]],
    ['판단 가설 · 확인된 심리나 경험이 아닙니다',(core.reasoning_rules||[]).map(r=>`${r.trigger} → ${r.value} / ${r.tradeoff} → ${r.conditional_choice}\n근거 필드: ${r.basis_fields.join(', ')} · 확인할 점: ${r.unknowns.join(', ')||'미확인'}`)],
    ['근거가 있는 사건',(core.timeline||[]).map(t=>`${t.when} · ${t.event_quote} [${t.source_id}]`)],
    ['자료와 미확인 항목',[...(core.evidence_anchors||[]).map(a=>`L${a.level} [${a.source_id}]: ${a.quote}`),...(session.states[c.id]||c.session_state).unresolved_issues]]
  ]){const heading=document.createElement('h3');heading.textContent=title;root.append(heading);for(const text of lines.length?lines:['제공된 근거가 없습니다.']){const p=document.createElement('p');p.textContent=text;root.append(p);}}
  $('profile').showModal();
}
function renderSuggestions(){
  $('suggestions').replaceChildren();
  for(const q of session.suggestions||[]){const b=document.createElement('button');b.className='question-chip';b.textContent=q.question;b.title=q.why;b.disabled=busy;b.onclick=()=>{$('ask-question').value=q.question;saveDraft();updateCounters();$('ask-question').focus();};$('suggestions').append(b);}
}
function renderCalibration(){
  const result=session?.calibration;
  $('calibration').textContent=result?JSON.stringify(result.metrics||result,null,2):'';
  $('calibration-stale').hidden=!result||!(session.report_stale||(session.calibration_revision??null)!==(session.report_revision??null));
}
function stopPoll(){pollGeneration++;if(polling)clearInterval(polling);polling=null;}
async function action(message,fn){
  if(busy)return;busy=true;$('status').textContent=message;syncButtons();
  try{await fn();$('status').textContent='';return true;}
  catch(e){$('status').textContent='진행하지 못했습니다: '+e.message;if(session){try{stopPoll();save(await api(`/api/sessions/${session.id}`));renderInterview();}catch{}}return false;}
  finally{busy=false;stopPoll();syncButtons();}
}
function poll(){
  stopPoll();const generation=pollGeneration;
  polling=setInterval(async()=>{
    if(!session||!busy||pollInFlight)return;pollInFlight=true;const id=session.id,version=writeVersion;
    try{const s=await api(`/api/sessions/${id}`);if(generation!==pollGeneration||!busy||session?.id!==id||version!==writeVersion)return;save(s,true);renderInterview();}
    catch{}finally{pollInFlight=false;}
  },2000);
}
function renderTargets(){
  $('targets').replaceChildren();for(const t of session.targets){const d=document.createElement('div');d.className='card';const label=document.createElement('label'),c=document.createElement('input'),title=document.createElement('strong');c.type='checkbox';c.value=t.id;title.textContent=t.segment_name;label.append(c,title);d.append(label);
    for(const [key,text] of [['segment_name','어떤 이용자인가요?'],['why_relevant','이 이용자를 추천하는 이유'],['problem_exposure','문제를 겪을 수 있는 상황'],['expected_current_alternative','사용할 것으로 예상되는 대안'],['buying_role','도입·구매 과정의 역할']]){const l=document.createElement('label');l.textContent=text;const input=document.createElement(['why_relevant','problem_exposure','expected_current_alternative'].includes(key)?'textarea':'input');input.className='target-field';input.value=t[key];input.required=['segment_name','why_relevant'].includes(key);input.dataset.field=key;input.dataset.id=t.id;if(key==='segment_name')input.addEventListener('input',()=>title.textContent=input.value);l.append(input);d.append(l);counter(input,limits.target_field);}
    const confidence={low:'낮음',medium:'중간',high:'높음'};const p=document.createElement('p');p.textContent=`근거 L${t.evidence_level} · 확신 ${confidence[t.confidence]||t.confidence} · 확인할 점: ${t.critical_unknowns.join(', ')||'미확인'}`;d.append(p);$('targets').append(d);
  }$('target-section').hidden=false;
}
function renderCards(){
  $('cards').replaceChildren();$('cards').hidden=!session.cards.length;
  for(const c of session.cards){
    const wrapper=document.createElement('article');wrapper.className='selected-persona';
    const profile=document.createElement('button');profile.className='profile-chip';profile.dataset.readonly='true';const name=document.createElement('strong');name.textContent=personaName(c);const segment=document.createElement('small');segment.textContent=segmentText(c);profile.append(name,segment);profile.title='상세 프로필 보기';profile.onclick=()=>openProfile(c);wrapper.append(profile);
    const box=document.createElement('details'),title=document.createElement('summary');title.textContent=`${personaName(c)} · 고급: 상세 카드 JSON 보기/수정`;
    const text=document.createElement('textarea');text.className='card-editor';text.value=JSON.stringify(c,null,2);
    const button=document.createElement('button');button.textContent='수정 후 다시 검사';button.dataset.cardEdit='true';button.disabled=busy||session.status!=='SELECTED';
    button.onclick=()=>action('수정한 카드의 근거와 모순을 검사합니다…',async()=>{if(!text.checkValidity())throw Error('카드 글자수 한도를 확인하세요.');save(await api(`/api/sessions/${session.id}/cards/${c.id}`,JSON.parse(text.value)));renderCards();renderInterview();});
    box.append(title,text);counter(text,limits.card_json);box.append(button);wrapper.append(box);$('cards').append(wrapper);
  }
  updateRun();
}
function renderInterview(){
  $('interview-section').hidden=!session.cards.length;
  const log=$('transcript'),bottom=scrollChatOnNextRender||log.scrollHeight-log.scrollTop-log.clientHeight<90,position=log.scrollTop;
  const name=pid=>personaName(session.cards.find(c=>c.id===pid))||pid;
  const signature=JSON.stringify([session.id,session.transcript.length,session.transcript.at(-1)?.id,session.chat_events,session.cards.map(c=>identityLabel(c)),optimisticMessage]);
  if(signature!==lastLogSignature){
  lastLogSignature=signature;log.replaceChildren();$('private-transcript').replaceChildren();$('participants').replaceChildren();
  for(const c of session.cards){const b=document.createElement('button');b.className='profile-chip';b.dataset.readonly='true';const strong=document.createElement('strong');strong.textContent=personaName(c);const sub=document.createElement('small');sub.textContent=segmentText(c);b.append(strong,sub);b.title=identityLabel(c)+' · 가상 이름 · 프로필 보기';b.onclick=()=>openProfile(c);$('participants').append(b);}
  const note=(text,role='moderator')=>{const d=document.createElement('div');d.className=role==='founder'?'founder-message':'moderator-message';d.textContent=text;log.append(d);};
  if(!session.chat_events?.length)note(session.transcript.length?'저장된 대화입니다. 아래 메시지 칸에서 계속 질문할 수 있습니다.':'첫 메시지를 보내 주세요. 참여자들이 자신의 조건을 설명하고 서로의 의견을 확인하며 대화를 이어갑니다.');
  let previousQuestion='';
  for(let i=0;i<=session.transcript.length;i++){
    for(const e of session.chat_events||[])if(e.before===i)note(e.content,e.role);
    if(i===session.transcript.length)break;
    const t=session.transcript[i],isPrivate=t.phase==='pre'||t.phase==='post';
    if(!isPrivate&&(!session.chat_events?.length||i<session.chat_events[0].before)&&!t.reply_to&&previousQuestion!==t.question){note(t.question);previousQuestion=t.question;}
    const row=document.createElement('div');row.className=`chat-row participant-${session.cards.findIndex(c=>c.id===t.persona_id)%3}`;
    const avatar=document.createElement('span');avatar.className='avatar';avatar.textContent=name(t.persona_id).slice(-2);avatar.setAttribute('aria-hidden','true');
    const body=document.createElement('div');body.className='message-body';const author=document.createElement('button');author.className='speaker-name';author.dataset.readonly='true';const card=session.cards.find(c=>c.id===t.persona_id);author.textContent=(card?identityLabel(card):t.persona_id)+(isPrivate?` · 비공개 ${t.phase==='pre'?'사전':'사후'} 의견`:'');author.onclick=()=>card&&openProfile(card);
    const bubble=document.createElement('div');bubble.className='chat-bubble';
    if(t.reply_to){const peer=session.transcript.find(x=>x.id===t.reply_to);if(peer){const quote=document.createElement('div');quote.className='reply-preview';quote.textContent=`↳ ${name(peer.persona_id)}: ${displayText(peer.content).slice(0,90)}`;bubble.append(quote);}}
    const p=document.createElement('p');p.textContent=displayText(t.content);bubble.append(p);
    const withheld=(t.quality_flags||[]).some(flag=>flag.endsWith('_withheld'));
    if(withheld){const caution=document.createElement('p');caution.className='answer-caution';caution.textContent='응답 귀속을 확인하지 못해 앞선 독립 의견을 유지했습니다. 새 비교는 보류합니다.';bubble.append(caution);}
    const detail=document.createElement('details');detail.className='turn-detail';const title=document.createElement('summary');title.textContent=withheld?'응답 귀속 안내 · 질문과 판단 근거':t.quality_flags?.length?'질문과 판단 근거 · 확인 안내':'질문과 판단 근거';const text=document.createElement('p');text.textContent=t.question+'\n판단 이유: '+t.reason+'\n판단 가설: '+(t.reasoning_rule_ids||[]).join(', ')+(t.thread_id?' · 질문 묶음: '+t.thread_id:'')+(t.quality_flags?.length?'\n확인 항목: '+t.quality_flags.join(', '):'');detail.append(title,text);
    body.append(author,bubble,detail);row.append(avatar,body);(isPrivate?$('private-transcript'):log).append(row);
  }
  if(optimisticMessage?.sessionId===session.id&&!(session.chat_events||[]).slice(optimisticMessage.eventCount).some(e=>e.role==='founder'&&e.content===optimisticMessage.content))note(optimisticMessage.content,'founder');
  if(bottom)log.scrollTop=log.scrollHeight;else log.scrollTop=position;
  scrollChatOnNextRender=false;
  $('changes').replaceChildren();for(const c of session.cards){const pre=session.transcript.find(t=>t.persona_id===c.id&&t.phase==='pre'),post=session.transcript.filter(t=>t.persona_id===c.id&&t.phase==='post').at(-1);if(pre&&post){const p=document.createElement('p');p.textContent=`${personaName(c)}: ${pre.stance} → ${post.stance} · 최종 판단 이유: ${displayText(post.reason)}`;$('changes').append(p);}}
  }
  $('chat-live').textContent=session.error?(pendingQuestion()?'응답이 중단되었습니다. ‘중단된 응답 이어받기’로 같은 메시지의 응답을 계속 받을 수 있습니다.':'응답이 중단되었습니다. 메시지를 다시 보내 저장된 차례부터 이어갈 수 있습니다.'):session.pending_speaker?`${name(session.pending_speaker)} 응답 생성 중…`:session.status==='REPORT'?'리포트를 작성하고 있습니다. 다음 메시지는 지금 작성해 두셔도 됩니다.':session.status==='COMPLETE'?'리포트가 준비되었습니다. 이 메시지 칸에서 계속 대화할 수 있습니다.':session.status==='WAITING'?'궁금한 점을 같은 메시지 칸에서 계속 물어보세요.':session.status==='SELECTED'?'페르소나가 준비되었습니다. 아래 메시지 칸에서 대화를 시작하세요.':busy?'대화를 준비하고 있습니다…':'';
  $('report-section').hidden=!session.report;$('report-stale').hidden=!session.report||!session.report_stale;
  const reportSignature=JSON.stringify([session.report,session.cards.map(c=>personaName(c))]);
  if(session.report&&reportSignature!==lastReportSignature){lastReportSignature=reportSignature;$('report').replaceChildren();const notice=document.createElement('p');notice.textContent=displayText(session.report.notice);$('report').append(notice);for(const [name,rows] of Object.entries(session.report.sections)){const d=document.createElement('div');d.className='report-block';const h=document.createElement('h3');h.textContent=name;d.append(h);for(const row of rows){const p=document.createElement('p');p.textContent=displayText(row.text).replace(/\bp[1-3]\b/g,pid=>personaName(session.cards.find(c=>c.id===pid)))+` [가설 · L${row.evidence_level} · ${row.confidence} · ${row.utterance_ids.join(', ')}]`;d.append(p);}$('report').append(d);}}
  renderSuggestions();renderCalibration();updateRun();
}
async function init(){
  limits=await api('/api/limits');for(const [name,text] of questions){if(!name){const h=document.createElement('h3');h.className='question-heading';h.textContent=text;$('fields').append(h);continue;}const l=document.createElement('label');l.textContent=text;const t=document.createElement(name==='q1'?'input':'textarea');t.name=name;t.required=name==='q1';l.append(t);$('fields').append(l);counter(t,limits[name]);}
  (await api('/api/categories')).forEach(v=>{const o=document.createElement('option');o.textContent=v;$('category').append(o);});for(const id of ['custom-name','custom-why','custom-exposure','custom-role'])counter($(id),limits.target_field);counter($('idea').elements.evidence,22000);counter($('ask-question'),limits.question);counter($('annotation'),limits.annotation_json);
  const h=await api('/api/health');$('mode').textContent=h.mode==='mock'?'MOCK · 합성 데모':h.model_server?.connected?`QWEN · ${h.model_server.model_file||h.model} · 문맥 ${h.model_server.effective_context_size}`:'QWEN · 모델 서버 연결 안 됨';
  const saved=new URLSearchParams(location.search).get('session')||localStorage.getItem('persona-session');try{const s=saved?await api(`/api/sessions/${saved}`):await api('/api/latest');if(s){save(s);for(const n of ['q1','q2','q3_1','q3_2','q4_1','q5'])$('idea').elements[n].value=s.input[n]||'';$('idea').elements.evidence.value=JSON.stringify(s.input.evidence,null,2);restoreDraft();renderTargets();renderCards();renderInterview();$('status').textContent='';if(s.cards.length)$('lounge-pane').scrollIntoView({block:'start'});}}catch(e){$('status').textContent='저장된 대화를 불러오지 못했습니다: '+e.message;}
}
init().catch(e=>$('status').textContent=e.message);
$('sample').onclick=()=>{const f=$('idea');f.elements.q1.value='예비창업자 인터뷰 질문 준비 도구';f.elements.q3_1.value='타깃 추천, 가상 인터뷰, 비교 리포트로 고객 인터뷰 준비의 어려움을 줄입니다.';f.elements.q3_2.value='기관 라이선스 이후 개인 구독';f.elements.q4_1.value='교내 창업 프로그램에서 PoC를 진행합니다.';f.elements.q5.value='IT';updateCounters();};
$('idea').onsubmit=e=>{e.preventDefault();action('아이디어에 맞는 이용자 유형을 추천하고 검사하고 있습니다…',async()=>{const data=Object.fromEntries(new FormData(e.target));data.evidence=JSON.parse(data.evidence||'[]');if(!Array.isArray(data.evidence))throw Error('근거는 JSON 배열로 입력하세요.');if(data.evidence.length>limits.evidence_count||data.evidence.some(x=>typeof x.text!=='string'||chars(x.text)>limits.evidence_text)||data.evidence.reduce((n,x)=>n+chars(x.text),0)>limits.evidence_total)throw Error('근거는 최대 8개, text 각각 1,500자, text 합계 6,000자까지입니다.');save(await api('/api/sessions',data));restoreDraft();renderTargets();renderCards();renderInterview();});};
$('recommend-targets').onclick=()=>action('저장된 아이디어로 타깃을 다시 추천하고 검사하고 있습니다…',async()=>{save(await api(`/api/sessions/${session.id}/targets/recommend`,{}));renderTargets();renderCards();renderInterview();});
$('select').onclick=async()=>{
  const ok=await action('페르소나를 생성하고 독립적으로 검사하고 있습니다…',async()=>{const custom=[];for(const c of $('targets').querySelectorAll('input[type=checkbox]:checked')){const t=structuredClone(session.targets.find(x=>x.id===c.value));for(const field of $('targets').querySelectorAll('[data-field]'))if(field.dataset.id===t.id){if(!field.checkValidity())throw Error(field.validity.valueMissing?'이용자 유형과 추천 이유를 입력하세요.':'타깃 입력은 각 300자까지입니다.');t[field.dataset.field]=field.value;}custom.push(t);}if($('custom-name').value.trim())custom.push({segment_name:$('custom-name').value,why_relevant:$('custom-why').value||'사용자 추가 가설',problem_exposure:$('custom-exposure').value||'UNKNOWN',buying_role:$('custom-role').value||'UNKNOWN'});if(custom.length<1||custom.length>3)throw Error('타깃을 1~3개 선택·추가하세요.');save(await api(`/api/sessions/${session.id}/select`,{custom_targets:custom}));renderCards();renderInterview();});
  if(ok){$('lounge-pane').scrollIntoView({behavior:'smooth',block:'start'});$('ask-question').focus({preventScroll:true});}
};
$('run').onclick=()=>action('저장된 이전 인터뷰를 이어받습니다…',async()=>{poll();save(await api(`/api/sessions/${session.id}/run`,{}));renderInterview();});
$('get-suggestions').onclick=async()=>{
  $('suggestions-status').textContent='현재 아이디어와 페르소나에 맞는 질문을 만들고 있습니다…';
  const ok=await action('질문을 추천하고 있습니다. 메시지는 미리 작성할 수 있습니다…',async()=>{save(await api(`/api/sessions/${session.id}/suggestions`,{}));renderSuggestions();});
  $('suggestions-status').textContent=ok?'질문을 눌러 메시지 칸에 넣은 뒤 자유롭게 수정하세요.':'질문 추천을 받지 못했습니다. 직접 메시지를 보내도 됩니다.';
};
async function sendMessage(question,personaId=null,interaction='interactive',retry=false){
  if(busy||!session)return;
  if(!question.trim()||chars(question)>limits.question){$('status').textContent=`메시지를 1~${limits.question}자로 입력하세요.`;$('ask-question').focus();return;}
  const original=question,id=session.id;
  const ok=await action(retry?'중단된 메시지의 응답을 이어받습니다…':'페르소나들이 메시지에 답하고 서로의 조건을 확인합니다…',async()=>{
    if(!retry){optimisticMessage={sessionId:id,content:question,eventCount:session.chat_events?.length||0};$('ask-question').value='';saveDraft();updateCounters();scrollChatOnNextRender=true;renderInterview();}
    poll();save(await api(`/api/sessions/${id}/ask`,{question,persona_id:personaId,interaction}));renderInterview();
  });
  optimisticMessage=null;
  // Preserve a draft typed while the response was being generated. Restore a failed first message only when no newer draft exists.
  if(!ok&&!retry&&!pendingQuestion()&&session?.id===id&&!$('ask-question').value){$('ask-question').value=original;saveDraft();updateCounters();}
  if(session?.id===id)renderInterview();$('ask-question').focus({preventScroll:true});
}
$('ask').onclick=()=>sendMessage($('ask-question').value,null,'interactive');
$('retry-question').onclick=()=>{const q=pendingQuestion();if(q)sendMessage(q.key[0],q.key[1],q.key[2],true);};
$('finish').onclick=()=>action('대화를 바탕으로 비교 리포트를 만들고 있습니다…',async()=>{poll();save(await api(`/api/sessions/${session.id}/finish`,{}));renderInterview();});
$('profile-close').onclick=()=>$('profile').close();
$('ask-question').addEventListener('input',saveDraft);
$('ask-question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!$('ask').disabled)$('ask').click();}});
$('download').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(session,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=`persona-studio-${session.id}.json`;a.click();URL.revokeObjectURL(u);};
$('calibrate').onclick=()=>action('실제 인터뷰 주석과 비교하고 있습니다…',async()=>{await api(`/api/sessions/${session.id}/calibrate`,JSON.parse($('annotation').value));save(await api(`/api/sessions/${session.id}`));renderCalibration();});
