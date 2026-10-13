'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const jsxRuntime = require('react/jsx-runtime');

function load(relativePath, dependencies, globals = {}) {
  const filename = path.join(__dirname, '..', 'src', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX }, fileName: filename,
  }).outputText;
  const exported = {};
  vm.runInNewContext(output, { exports: exported, module: { exports: exported }, ...globals, require(name) { assert.ok(Object.hasOwn(dependencies, name), 'Unexpected dependency: ' + name); return dependencies[name]; } }, { filename });
  return exported;
}

function deferred() { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; }
const proposal = (status = 'discussion', extra = {}) => ({ status, id: 'recommendation-1', revision: 2, question: '운영 시간이 늘어나면 어떤 조건에서 도입을 포기하나요?', why: '두 사람의 허용 가능한 운영 부담이 달랐고 중단 조건은 아직 비교하지 않았습니다.', source_utterance_ids: ['u1'], missing_information: [], ...extra });
const initialSession = () => ({ id: 'session-1', input: {}, mode: 'mock', status: 'GROUP', cards: [{ id: 'p1', presentation: { display_name: '김하늘' }, immutable_core: { identity_context: { segment: '카페 운영자' } } }], suggestions: [], dialogue_runtime: {}, transcript: [{ id: 'u1', persona_id: 'p1', phase: 'group', content: '시간이 부족합니다.' }, { id: 'u2', persona_id: 'p1', phase: 'group', content: '운영 부담을 비교합니다.' }], threads: [{ id: 'thread-1', question: '도입할까요?', status: 'returned_to_user', remaining_issues: ['운영 부담'], stop_reason: 'no_grounded_expansion' }], chat_events: [] });

// Exercise handlers and asynchronous UI state without network, model or browser.
function setup(fetchRecommendation) {
  let session = initialSession(), selectedSession = session.id, cursor = 0;
  const hooks = [], pendingEffects = [], calls = [], sends = [];
  function slot(initial) { const index = cursor++; if (!hooks[index]) hooks[index] = initial(); return hooks[index]; }
  const React = {
    Fragment: Symbol.for('react.fragment'),
    useState(initial) { const saved = slot(() => ({ value: typeof initial === 'function' ? initial() : initial })); return [saved.value, value => { saved.value = typeof value === 'function' ? value(saved.value) : value; }]; },
    useRef(initial) { return slot(() => ({ current: initial })); },
    useEffect(callback, deps) { const saved = slot(() => ({ deps: undefined, cleanup: undefined })); if (!saved.deps || deps.some((value, index) => value !== saved.deps[index])) pendingEffects.push(() => { saved.cleanup?.(); saved.cleanup = callback(); saved.deps = deps; }); },
  };
  const parts = Object.fromEntries(['ChatComposer', 'ChatRoomHeader', 'PersonaMessage', 'QuestionChips', 'TypingMessage', 'UserMessage'].map(name => [name, function Component() {}]));
  const api = { currentSessionId: () => selectedSession, getSession: async () => session, rememberSession() {}, runSessionAction: async (...args) => sends.push(args) };
  const next = load('lib/next-question.ts', { './soul-api': { api: async (url, body, signal) => { calls.push({ url, body, signal }); return fetchRecommendation(url, body, signal); } } });
  const { ChatClient } = load('app/(app)/chat/ChatClient.tsx', {
    'react/jsx-runtime': jsxRuntime, react: React, 'next/link': { default: function Link() {} }, 'next/navigation': { useRouter: () => ({ push() {} }) },
    '@/components/AppHeader': { AppHeader: function AppHeader() {} }, '@/components/chat/ChatParts': parts,
    '@/lib/soul-api': api, '@/lib/use-soul-session': { useSoulSession: () => ({ session, loading: false, error: null }) },
    '@/lib/persona-presentation': { cardColor: () => 1 }, '@/components/IdeaSummary': { IdeaSummary: function IdeaSummary() {} },
    '@/lib/chat-presentation': { displayChatText: value => value }, '@/lib/next-question': next, './DmPanel': { DmPanel: function DmPanel() {} },
  }, { AbortController, localStorage: { setItem() {}, removeItem() {}, getItem: () => null }, setInterval: () => 1, clearInterval() {} });
  let tree;
  function render() { cursor = 0; tree = ChatClient({}); for (const effect of pendingEffects.splice(0)) effect(); return tree; }
  function allNodes(node) { if (!node || typeof node !== 'object') return []; if (Array.isArray(node)) return node.flatMap(allNodes); return [node, ...allNodes(node.props?.children)]; }
  function button(label) { return allNodes(tree).find(node => node.type === 'button' && node.props.children === label); }
  function composer() { return allNodes(tree).find(node => node.type === parts.ChatComposer).props; }
  function text() { return allNodes(tree).flatMap(node => Array.isArray(node.props?.children) ? node.props.children : [node.props?.children]).filter(value => typeof value === 'string').join(' '); }
  render();
  return { render, button, composer, text, calls, sends, setSession(value) { session = value; selectedSession = value.id; }, selectSession(id) { selectedSession = id; }, cleanup() { for (const hook of hooks) hook?.cleanup?.(); } };
}

const flush = async () => { for (let index = 0; index < 8; index++) await Promise.resolve(); };

test('button fetches a revision-bound recommendation, fills the existing composer once, and never sends it', async () => {
  const env = setup(async () => proposal());
  env.button('이 쟁점 더 살펴보기').props.onClick(); await flush(); env.render();
  assert.equal(env.calls[0].url, '/sessions/session-1/next-question');
  assert.equal(env.calls[0].body.revision, 2);
  assert.equal(env.composer().value, proposal().question);
  assert.equal(env.sends.length, 0);
  assert.match(env.text(), /중단 조건은 아직 비교하지 않았습니다/);
  assert.equal(env.button('이 쟁점 더 살펴보기'), undefined, 'Same revision cannot re-paste an offered question');
});

test('a late recommendation preserves text typed while the request was pending', async () => {
  const request = deferred(), env = setup(() => request.promise);
  env.button('이 쟁점 더 살펴보기').props.onClick(); env.render();
  assert.match(env.text(), /다음 질문이 필요한지 검토/);
  assert.equal(env.composer().sending, true);
  env.composer().onChange('직원이 한 명인 경우를 먼저 묻고 싶습니다.');
  request.resolve(proposal()); await flush(); env.render();
  assert.equal(env.composer().value, '직원이 한 명인 경우를 먼저 묻고 싶습니다.');
  assert.match(env.text(), /작성 중인 질문을 유지했어요/);
  assert.equal(env.sends.length, 0);
});

test('evidence requests show the missing information and interview question without pretending personas can answer', async () => {
  const env = setup(async () => proposal('needs_evidence', { missing_information: ['카페의 실제 세척 시간'], question: '최근 세척 업무에 얼마나 시간이 들었나요?' }));
  env.composer().onChange('작성해 둔 질문'); env.render();
  env.button('이 쟁점 더 살펴보기').props.onClick(); await flush(); env.render();
  assert.equal(env.composer().value, '작성해 둔 질문');
  assert.match(env.text(), /카페의 실제 세척 시간/);
  assert.match(env.text(), /최근 세척 업무에 얼마나 시간이 들었나요/);
  assert.match(env.text(), /고객 인터뷰나 운영 자료로 확인/);
  assert.equal(env.button('이 쟁점 더 살펴보기'), undefined);
  assert.equal(env.sends.length, 0);
});

test('no new question explains the boundary and removes the repeated continuation loop', async () => {
  const env = setup(async () => proposal('no_new_question', { question: '', why: '현재 조건에서 비교할 차이는 모두 다뤘습니다.' }));
  env.button('이 쟁점 더 살펴보기').props.onClick(); await flush(); env.render();
  assert.equal(env.composer().value, '');
  assert.match(env.text(), /현재 조건에서 비교할 차이는 모두 다뤘습니다/);
  assert.equal(env.button('이 쟁점 더 살펴보기'), undefined);
});

test('an evidence-only result labels missing material without inventing an interview question', async () => {
  const env = setup(async () => proposal('needs_evidence', { question: '', missing_information: ['추천한 타깃과 실제 구매자의 일치 여부'], why: '실제 고객 모집 결과가 필요합니다.' }));
  env.composer().onChange('사용자가 작성한 질문'); env.render();
  env.button('이 쟁점 더 살펴보기').props.onClick(); await flush(); env.render();
  assert.match(env.text(), /실제 자료가 필요한 부분/);
  assert.match(env.text(), /추천한 타깃과 실제 구매자의 일치 여부/);
  assert.doesNotMatch(env.text(), /실제 고객에게 확인할 질문/);
  assert.equal(env.composer().value, '사용자가 작성한 질문');
  assert.equal(env.button('이 쟁점 더 살펴보기'), undefined);
  assert.equal(env.sends.length, 0);
});

test('late results cannot populate a different selected session or an advanced conversation', async () => {
  for (const change of ['selected', 'session', 'thread', 'revision']) {
    const request = deferred(), env = setup(() => request.promise);
    env.button('이 쟁점 더 살펴보기').props.onClick();
    if (change === 'selected') env.selectSession('session-2');
    if (change === 'session') env.setSession({ ...initialSession(), id: 'session-2' });
    if (change === 'thread') env.setSession({ ...initialSession(), threads: [{ ...initialSession().threads[0], id: 'thread-2' }] });
    if (change === 'revision') env.setSession({ ...initialSession(), transcript: [...initialSession().transcript, { id: 'u3', phase: 'group' }] });
    env.render(); request.resolve(proposal()); await flush(); env.render();
    assert.equal(env.composer().value, '', change);
    assert.doesNotMatch(env.text(), /다음 질문을 제안한 이유/, change);
    assert.equal(env.sends.length, 0);
  }
});

test('a recommendation with the wrong revision is rejected and remains explicitly retryable', async () => {
  const env = setup(async () => proposal('discussion', { revision: 1 }));
  env.button('이 쟁점 더 살펴보기').props.onClick(); await flush(); env.render();
  assert.equal(env.composer().value, '');
  assert.match(env.text(), /대화가 바뀌었습니다/);
  assert.ok(env.button('이 쟁점 더 살펴보기'));
});

test('unmount aborts a pending recommendation without filling or sending a draft', async () => {
  const request = deferred(), env = setup(() => request.promise);
  env.button('이 쟁점 더 살펴보기').props.onClick(); env.cleanup();
  assert.equal(env.calls[0].signal.aborted, true);
  request.resolve(proposal()); await flush(); env.render();
  assert.equal(env.composer().value, '');
  assert.equal(env.sends.length, 0);
});
