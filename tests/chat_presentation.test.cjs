'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(relativePath, dependencies = {}) {
  const filename = path.join(__dirname, '..', 'src', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX }, fileName: filename,
  }).outputText;
  const exported = {};
  vm.runInNewContext(output, { exports: exported, module: { exports: exported }, require(name) { assert.ok(Object.hasOwn(dependencies, name), 'Unexpected dependency: ' + name); return dependencies[name]; } }, { filename });
  return exported;
}
const korean = load('lib/korean-text.ts');
const chat = load('lib/chat-presentation.ts', { './korean-text': korean });
const parts = load('components/chat/ChatParts.tsx', {
  'react/jsx-runtime': require('react/jsx-runtime'),
  '@/components/PersonaAvatar': { PersonaAvatar: ({ name }) => React.createElement('span', { 'data-name': name }, name) },
  '@/lib/korean-text': korean,
  '@/lib/chat-presentation': chat,
});
const people = [{ id: 'p1', name: '김하늘', color: 1 }, { id: 'p2', name: '이다온', color: 2 }, { id: 'p3', name: '박시온', color: 3 }];

test('a group question header shows its actual interaction instead of a fixed directed-question status', () => {
  const html = renderToStaticMarkup(React.createElement(parts.ChatRoomHeader, { personas: people, round: 2, interaction: 'auto', onOpenDm() {} }));
  assert.match(html, /질문 2개/);
  assert.match(html, /모두 · 상호 대화/);
  assert.doesNotMatch(html, /지정 답변/);
  assert.match(html, /한 명에게 묻기/);
  assert.match(html, /김하늘님에게 지정 질문/);
});

test('a real directed question remains distinct from a group interaction', () => {
  const direct = renderToStaticMarkup(React.createElement(parts.ChatRoomHeader, { personas: people, round: 1, interaction: 'direct', onOpenDm() {} }));
  assert.match(direct, /지정 답변/);
  assert.doesNotMatch(direct, /모두 · 상호 대화/);
  assert.equal(chat.chatInteractionLabel('interactive'), '모두 · 상호 대화');
});

test('chat hides citation-only rule labels and identifies peer conditions by their real display name', () => {
  const input = '불명확 으로 남습니다 (p2:rr1). p1:r1 에 따르면 제 조건은 다릅니다. p3:r1은 시간 제약입니다.';
  const expected = '불명확으로 남습니다. 제 판단 조건에 따르면 제 조건은 다릅니다. 박시온님의 판단 조건은 시간 제약입니다.';
  const displayed = chat.displayChatText(input, 'p1', people);
  assert.equal(displayed, expected);
  assert.equal(chat.displayChatText(displayed, 'p1', people), displayed);
  assert.equal(input, '불명확 으로 남습니다 (p2:rr1). p1:r1 에 따르면 제 조건은 다릅니다. p3:r1은 시간 제약입니다.', 'Input remains the raw transcript text');
});

test('rule display cleanup is restricted and preserves literal source quotations, code, URLs and unrelated identifiers', () => {
  const input = '"p1:r1 에 따르면"와 ‘(p2:rr1)’는 인용입니다. `p3:r1` https://example.org/p1:r1 source_p1:r1 p1:r10 rr12X p2:rr3 p4:r1은 원문입니다.';
  assert.equal(chat.displayChatText(input, 'p1', people), input);
  assert.equal(chat.displayChatText('(r1, p2:rr2) r2에 따른 조건', 'p1', people), ' 제 판단 조건에 따른 조건');
});
test('known public utterance references show their owner while original literal citations remain intact', () => {
  const text='동료의 조건 [u6]을 비교합니다. [u99] "[u6]" ` [u6] ` https://example.org/[u6]';
  assert.equal(chat.displayChatText(text,'p1',people,{u6:'김하린'}),'동료의 조건 [김하린님 발언]을 비교합니다. [u99] "[u6]" ` [u6] ` https://example.org/[u6]');
});
