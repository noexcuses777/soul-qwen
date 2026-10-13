'use strict';
// Pure module behavior only. No browser, real network, model or session DB.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const legacyKorean = require('../frontend/korean-text.js');

function loadModule(file, globals = {}, dependencies = {}) {
  const filename = path.join(__dirname, '..', 'src', 'lib', file + '.ts');
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    fileName: filename,
  }).outputText;
  const exported = {};
  const context = vm.createContext({
    exports: exported, module: { exports: exported }, ...globals,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), 'Unexpected module dependency: ' + name);
      return dependencies[name];
    },
  });
  vm.runInContext(output, context, { filename });
  return exported;
}

const korean = loadModule('korean-text');
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function response(status, payload) {
  return { status, ok: status >= 200 && status < 300, json: async () => payload };
}
function setup(fetcher) {
  const storage = new Map(), events = [], requests = [], intervals = new Map();
  let nextTimer = 1, blockedStorage = false;
  const api = loadModule('soul-api', {
    fetch: async (url, options) => { requests.push({ url, ...options }); return fetcher(url, options); },
    localStorage: {
      getItem(key) { if (blockedStorage) throw Error('Storage disabled'); return storage.get(key) ?? null; },
      setItem(key, value) { if (blockedStorage) throw Error('Storage disabled'); storage.set(key, value); },
    },
    window: { dispatchEvent(event) { events.push(event); return true; } },
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail; } },
    setInterval(callback) { const id = nextTimer++; intervals.set(id, callback); return id; },
    clearInterval(id) { intervals.delete(id); },
  }, { './korean-text': korean });
  return { api, storage, events, requests, intervals,
    blockStorage() { blockedStorage = true; },
    poll() { assert.equal(intervals.size, 1); return [...intervals.values()][0](); },
  };
}
const session = (id, extra = {}) => ({ id, transcript: [], mode: 'mock', ...extra });

test('idea submission uses the Qwen backend API POST contract, not client answers', async () => {
  const final = session('created');
  const env = setup(async () => response(200, final));
  const idea = { q1: '고객 인터뷰 도구', q2: '', q3_1: '준비 부담', q3_2: '', q4_1: '', q5: 'IT', evidence: [] };
  assert.equal(await env.api.createSession(idea), final);
  const request = env.requests[0];
  assert.equal(request.url, '/api/sessions');
  assert.equal(request.method, 'POST');
  assert.equal(request.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(request.body), idea);
  assert.equal(request.cache, 'no-store');
  assert.deepEqual([...env.storage], [[env.api.SESSION_KEY, 'created']], 'Persist the ID only');
  assert.equal(env.events[0].type, env.api.SESSION_EVENT);
  assert.equal(env.events[0].detail, final);
});

test('session lookup encodes the identifier and preserves abort signals', async () => {
  const env = setup(async () => response(200, session('saved')));
  const signal = new AbortController().signal;
  await env.api.getSession('session/with?characters', signal);
  assert.equal(env.requests[0].url, '/api/sessions/session%2Fwith%3Fcharacters');
  assert.equal(env.requests[0].method, 'GET');
  assert.equal(env.requests[0].body, undefined);
  assert.equal(env.requests[0].signal, signal);
});

test('backend conflict and structured validation errors remain actionable', async () => {
  const env = setup(async url => url.endsWith('/conflict')
    ? response(409, { detail: 'Another local operation is running' })
    : response(422, { detail: [{ loc: ['body', 'q5'], msg: 'Required category' }] }));
  await assert.rejects(env.api.api('/conflict', {}), /진행 중인 작업.*Another local operation/);
  await assert.rejects(env.api.api('/invalid', {}), /Required category/);
  assert.equal(env.events.length, 0, 'Errors must not publish fabricated sessions');
});

test('unreadable and transport failures are exposed without a mock fallback', async () => {
  const env = setup(async url => {
    if (url.endsWith('/transport')) throw Error('Connection refused');
    return { status: 502, ok: false, json: async () => { throw Error('Not JSON'); } };
  });
  await assert.rejects(env.api.api('/unreadable'), /응답을 읽지 못했습니다 \(502\)/);
  await assert.rejects(env.api.api('/transport'), /Connection refused/);
  assert.equal(env.requests.length, 2);
  assert.equal(env.events.length, 0);
});

test('unknown fields are visibly unknown and known prose keeps conservative spacing', () => {
  const env = setup(async () => response(200, null));
  for (const value of ['UNKNOWN', '', null, undefined]) assert.equal(env.api.known(value), '아직 확인하지 못했어요');
  assert.equal(env.api.known('부족 이나 불명확 으로 남습니다.'), '부족이나 불명확으로 남습니다.');
  assert.equal(env.api.known('"부족 이나"라는 원문'), '"부족 이나"라는 원문');
});

test('disabled local storage still allows live session communication', () => {
  const env = setup(async () => response(200, null));
  env.blockStorage();
  const data = session('live');
  assert.equal(env.api.rememberSession(data), data);
  assert.equal(env.api.currentSessionId(), null);
  assert.equal(env.events[0].detail, data);
});

test('saved sessions are loaded directly without replacing them with latest', async () => {
  const env = setup(async () => response(200, session('saved')));
  env.storage.set(env.api.SESSION_KEY, 'saved');
  assert.equal((await env.api.getCurrentSession()).id, 'saved');
  assert.deepEqual(env.requests.map(x => x.url), ['/api/sessions/saved']);
});

test('a missing saved ID falls back only on actual HTTP 404', async () => {
  for (const detail of ['Session not found', '삭제된 세션입니다.']) {
    const env = setup(async url => url.endsWith('/latest')
      ? response(200, session('newest')) : response(404, { detail }));
    env.storage.set(env.api.SESSION_KEY, 'deleted');
    assert.equal((await env.api.getCurrentSession()).id, 'newest');
    assert.deepEqual(env.requests.map(x => x.url), ['/api/sessions/deleted', '/api/latest']);
    assert.equal(env.api.currentSessionId(), 'newest');
  }
});

test('server failures never silently switch to another session even with a 404-like message', async () => {
  const env = setup(async () => response(503, { detail: 'Session not found' }));
  env.storage.set(env.api.SESSION_KEY, 'saved');
  await assert.rejects(env.api.getCurrentSession(), /Session not found/);
  assert.deepEqual(env.requests.map(x => x.url), ['/api/sessions/saved']);
  assert.equal(env.api.currentSessionId(), 'saved');
});

test('aborted current-session reads do not fall back to latest', async () => {
  const controller = new AbortController();
  const env = setup(async () => {
    controller.abort();
    throw Error('Read aborted');
  });
  env.storage.set(env.api.SESSION_KEY, 'saved');
  await assert.rejects(env.api.getCurrentSession(controller.signal), /Read aborted/);
  assert.deepEqual(env.requests.map(x => x.url), ['/api/sessions/saved']);
});

test('no saved session and an empty backend remain an empty state', async () => {
  const env = setup(async () => response(200, null));
  assert.equal(await env.api.getCurrentSession(), null);
  assert.deepEqual(env.requests.map(x => x.url), ['/api/latest']);
  assert.equal(env.events.length, 0);
});

test('late GET polling cannot overwrite the completed POST session', async () => {
  const post = deferred(), poll = deferred(), progress = [];
  const env = setup(async (_, options) => options.method === 'POST' ? post.promise : poll.promise);
  const operation = env.api.runSessionAction('same', 'ask', { question: '조건을 비교해주세요.' }, s => progress.push(s));
  const pendingPoll = env.poll();
  const final = session('same', { transcript: [{ id: 'final' }] });
  post.resolve(response(200, final));
  assert.equal(await operation, final);
  poll.resolve(response(200, session('same', { transcript: [{ id: 'old' }] })));
  await pendingPoll;
  assert.deepEqual(progress.map(s => s.transcript[0].id), ['final']);
  assert.equal(env.events.at(-1).detail, final);
  assert.equal(env.intervals.size, 0);
});

test('persisted partial turns are published while generation continues without overlapping polls', async () => {
  const post = deferred(), poll = deferred(), progress = [];
  const env = setup(async (_, options) => options.method === 'POST' ? post.promise : poll.promise);
  const operation = env.api.runSessionAction('same', 'ask', { question: '질문' }, s => progress.push(s));
  const pendingPoll = env.poll();
  await env.poll();
  assert.equal(env.requests.filter(x => x.method === 'GET').length, 1);
  poll.resolve(response(200, session('same', { transcript: [{ id: 'partial' }] })));
  await pendingPoll;
  post.resolve(response(200, session('same', { transcript: [{ id: 'partial' }, { id: 'finished' }] })));
  await operation;
  assert.deepEqual(progress.map(s => s.transcript.length), [1, 2]);
  assert.equal(env.intervals.size, 0);
});

test('failed generation refreshes persisted retry state and ignores an older in-flight poll', async () => {
  const post = deferred(), oldPoll = deferred(), progress = [];
  let gets = 0;
  const partial = session('same', { pending_question: '다시 보낼 원래 질문', transcript: [{ id: 'persisted' }] });
  const env = setup(async (_, options) => options.method === 'POST'
    ? post.promise : ++gets === 1 ? oldPoll.promise : response(200, partial));
  const operation = env.api.runSessionAction('same', 'ask', { question: '다시 보낼 원래 질문' }, s => progress.push(s));
  const pendingPoll = env.poll();
  const rejected = assert.rejects(operation, /local model transport failed/);
  post.resolve(response(502, { detail: 'local model transport failed' }));
  await rejected;
  oldPoll.resolve(response(200, session('same', { transcript: [] })));
  await pendingPoll;
  assert.deepEqual(progress, [partial]);
  assert.equal(env.events.at(-1).detail, partial);
  assert.equal(env.intervals.size, 0);
});

test('failed recovery reads preserve the original model error and stop timers', async () => {
  const env = setup(async (_, options) => options.method === 'POST'
    ? response(502, { detail: 'Qwen context limit exceeded' }) : response(503, { detail: 'Recovery unavailable' }));
  await assert.rejects(env.api.runSessionAction('same', 'ask', {}), /Qwen context limit exceeded/);
  assert.equal(env.events.length, 0);
  assert.equal(env.intervals.size, 0);
});

test('selecting another session blocks both old progress and the old final mutation', async () => {
  const post = deferred(), poll = deferred(), progress = [];
  const env = setup(async (_, options) => options.method === 'POST' ? post.promise : poll.promise);
  env.storage.set(env.api.SESSION_KEY, 'old-session');
  const operation = env.api.runSessionAction('old-session', 'ask', {}, s => progress.push(s));
  const pendingPoll = env.poll();
  const selected = session('new-session');
  env.api.rememberSession(selected);
  poll.resolve(response(200, session('old-session', { transcript: [{ id: 'old-progress' }] })));
  await pendingPoll;
  post.resolve(response(200, session('old-session', { transcript: [{ id: 'old-final' }] })));
  await operation;
  assert.equal(env.api.currentSessionId(), 'new-session');
  assert.deepEqual(env.events.map(event => event.detail.id), ['new-session']);
  assert.deepEqual(progress, []);
});

test('an old non-polled action cannot replace a newly selected session', async () => {
  const post = deferred();
  const env = setup(async () => post.promise);
  env.storage.set(env.api.SESSION_KEY, 'old-session');
  const operation = env.api.sessionAction('old-session', 'names/p1', { display_name: '새 이름' });
  env.api.rememberSession(session('new-session'));
  post.resolve(response(200, session('old-session')));
  await operation;
  assert.equal(env.api.currentSessionId(), 'new-session');
  assert.deepEqual(env.events.map(event => event.detail.id), ['new-session']);
});

test('an earlier current-session read cannot publish over a newer selected session', async () => {
  const read = deferred();
  const env = setup(async () => read.promise);
  env.storage.set(env.api.SESSION_KEY, 'old-session');
  const pending = env.api.getCurrentSession();
  env.api.rememberSession(session('new-session'));
  read.resolve(response(200, session('old-session')));
  await pending;
  assert.equal(env.api.currentSessionId(), 'new-session');
  assert.deepEqual(env.events.map(event => event.detail.id), ['new-session']);
});

test('Next formatter preserves the established spacing, quotations, URLs, IDs and facts', () => {
  const cases = [
    ['불명확 으로 남습니다.', '불명확으로 남습니다.'],
    ['부족 이나 위험이 있는 가설입니다.', '부족이나 위험이 있는 가설입니다.'],
    ['조건 은 다르고 비용 이 부족합니다.', '조건은 다르고 비용이 부족합니다.'],
    ['교내 PoC 를 검토합니다.', '교내 PoC를 검토합니다.'],
    ['알수 없는 조건과 확인할수있습니다.', '알 수 없는 조건과 확인할 수 있습니다.'],
    ['하지만 이 조건과 정보 이 부분은 다릅니다.', '하지만 이 조건과 정보 이 부분은 다릅니다.'],
    ['"불명확 으로"와 ‘부족 이나’는 원문입니다.', '"불명확 으로"와 ‘부족 이나’는 원문입니다.'],
    ['`부족 이나`와 ```text\n불명확 으로\n```', '`부족 이나`와 ```text\n불명확 으로\n```'],
    ['https://example.org/불명확?query=부족%20이나', 'https://example.org/불명확?query=부족%20이나'],
    ['p1:r1, p2:r2, source_12, 19,900원, Qwen3.5-4B', 'p1:r1, p2:r2, source_12, 19,900원, Qwen3.5-4B'],
    ['서비스 은 자료와 기준 가 다릅니다.', '서비스 은 자료와 기준 가 다릅니다.'],
    ['부족\t이나\n불명확\u00a0으로', '부족이나\n불명확으로'],
  ];
  for (const [raw, expected] of cases) {
    const formatted = korean.normalize(raw);
    assert.equal(formatted, expected);
    assert.equal(formatted, legacyKorean.normalize(raw), 'Match the already verified legacy formatter');
    assert.equal(korean.normalize(formatted), formatted, 'Repeated rendering is idempotent');
    assert.equal(formatted.replace(/\s/g, ''), raw.replace(/\s/g, ''), 'No facts or particles are rewritten');
  }
});
