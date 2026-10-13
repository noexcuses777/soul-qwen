'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const filename = path.join(__dirname, '../src/lib/persona-presentation.ts');
const exported = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename,'utf8'), { compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
  { exports:exported, require:name => { assert.equal(name,'./soul-api'); return {known:value => value && value!=='UNKNOWN' ? value : '미확인'}; } });
const p = exported;
const targets = Array.from({length:8},(_,i)=>({id:`t${i+1}`,segment_name:`이용자 ${i+1}`,problem_exposure:'입력된 상황',critical_unknowns:['예산 미확인'],why_relevant:'입력된 이유',expected_current_alternative:'전화'}));
const card=(id,name,segment)=>({id,presentation:{display_name:name},immutable_core:{identity_context:{segment}}});

test('all candidates get unique fictional names without inventing unknown biography',()=>{
  const session={cards:[],targets};
  const people=p.targetPersonas(session,targets);
  assert.equal(new Set(people.map(x=>x.name)).size,8);
  assert.deepEqual(JSON.parse(JSON.stringify(people.map(x=>x.situation))),targets.map(x=>x.problem_exposure));
  for(const value of people) { assert.equal(value.age,undefined); assert.equal(value.gender,undefined); assert.equal(value.quote,undefined); }
  assert.deepEqual(p.targetPersonas(session,targets).map(x=>x.name),people.map(x=>x.name));
});

test('persisted random aliases survive reload, filtering and changed display order',()=>{
  const names=Object.fromEntries(targets.map((target,i)=>[target.id,`저장 이름 ${i+1}`]));
  const session={cards:[],targets,target_display_names:names};
  const first=p.targetPersonas(session,targets);
  const reordered=p.targetPersonas(JSON.parse(JSON.stringify(session)),[targets[7],targets[1],targets[3]]);
  for(const person of reordered) assert.equal(person.name,first.find(value=>value.id===person.id).name);
  assert.equal(p.targetPersonas(session,[{...targets[0],display_name:'직접 이름'}])[0].name,'직접 이름');
});
test('selection order does not change a selected persons name or color',()=>{
  const preview=p.targetPersonas({cards:[],targets},targets);
  const session={targets,selected_target_ids:['t6','t2'],cards:[card('p1',preview[5].name,targets[5].segment_name),card('p2',preview[1].name,targets[1].segment_name)]};
  const people=p.targetPersonas(session,targets);
  assert.equal(people[5].name,preview[5].name);
  assert.equal(p.cardColor(session,session.cards[0]),people[5].color);
  assert.equal(p.cardColor(session,session.cards[1]),people[1].color);
});
test('legacy card names and later renames win over stale local drafts',()=>{
  const session={targets,cards:[card('p1','서진',targets[4].segment_name)]};
  const people=p.targetPersonas(session,targets.map(x=>x.id==='t5'?{...x,display_name:'이전 이름'}:x));
  assert.equal(people[4].name,'서진');
  assert.equal(new Set(people.map(x=>x.name)).size,8);
});
test('editing one target does not rename or recolor unrelated candidates',()=>{
  const session={cards:[],targets};
  const before=p.targetPersonas(session,targets);
  const edited={...targets[0],display_name:'김서연'};
  const after=p.targetPersonas(session,[...targets.slice(1),edited]);
  assert.equal(after.find(value=>value.id==='t1').name,'김서연');
  for (const value of before.slice(1)) {
    const current=after.find(person=>person.id===value.id);
    assert.equal(current.name,value.name);
    assert.equal(current.color,value.color);
  }
});
test('custom presentation is stripped from model targets while selection names survive',()=>{
  const custom={...targets[3],id:'custom-test',display_name:'새 이름'};
  const all=[...targets,custom];
  const people=p.targetPersonas({cards:[],targets},all);
  const payload=p.selectionPayload([custom,targets[5]],[custom],people);
  assert.deepEqual(JSON.parse(JSON.stringify(payload.target_ids)),['t6']);
  assert.equal(payload.custom_targets[0].display_name,undefined);
  assert.equal(payload.custom_targets[0].segment_name,custom.segment_name);
  assert.equal(payload.display_names['custom-test'],'새 이름');
});
