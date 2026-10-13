'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const korean = require('../frontend/korean-text.js');

const repairs = [
  ['불명확 으로 남습니다.', '불명확으로 남습니다.'],
  ['부족 이나 위험이 있는 가설입니다.', '부족이나 위험이 있는 가설입니다.'],
  ['불확실성 으로는 판단하기 어렵습니다.', '불확실성으로는 판단하기 어렵습니다.'],
  ['상황 에서는 판단을 보류합니다.', '상황에서는 판단을 보류합니다.'],
  ['조건 은 다르고 비용 이 부족합니다.', '조건은 다르고 비용이 부족합니다.'],
  ['서비스 가 제공하는 기능 을 확인하세요.', '서비스가 제공하는 기능을 확인하세요.'],
  ['교내 PoC 를 검토하고 SaaS 의 비용을 확인합니다.', '교내 PoC를 검토하고 SaaS의 비용을 확인합니다.'],
  ['LLM 으로 AI 를 구성하나 UNKNOWN 으로 남습니다.', 'LLM으로 AI를 구성하나 UNKNOWN으로 남습니다.'],
  ['MVP 는 B2B 로 검토합니다.', 'MVP는 B2B로 검토합니다.'],
  ['부족\t이나\n불명확\u00a0으로', '부족이나\n불명확으로'],
  ['확인할수있습니다.', '확인할 수 있습니다.'],
  ['판단할 수없어요.', '판단할 수 없어요.'],
  ['알수 없는 사실과 바뀔수있는 조건입니다.', '알 수 없는 사실과 바뀔 수 있는 조건입니다.']
];
for (const [raw, expected] of repairs) test('repair: ' + raw, () => {
  assert.equal(korean.normalize(raw), expected);
  assert.equal(korean.normalize(expected), expected, 'formatting is idempotent');
  assert.equal(raw.replace(/\s/g, ''), expected.replace(/\s/g, ''), 'only whitespace may change');
});

const preserved = [
  '하지만 이 조건과 만약 이 상황은 다릅니다.',
  '새로운 이 도구를 제공한 대로 검토할 만큼 쓰세요.',
  '정보 이 부분은 추가 확인이 필요합니다.',
  '검증 이 후 자료를 확인해야 합니다.',
  '조건\n이나\n부족\n으로',
  '조건 이는 분리 오류가 아닙니다. 부족 이나리라는 제품입니다.',
  '고객_정보 으로 a조건 으로 고객_조건 은',
  'customer_PoC 를 PoC1 를 MySaaS 의 Qwen3.5-4B 를',
  'Qwen3.5-4B, p1:r1, source_12, 19,900원, 2026-10-04',
  'https://example.org/불명확?query=부족%20이나',
  '`불명확 으로`와 ```text\n부족 이나\n```는 그대로입니다.',
  '```text\n불명확 으로\n부족 이나',
  '"불명확 으로"와 ‘부족 이나’, “조건 은”은 인용문입니다.',
  '"PoC 를"과 `SaaS 의`라는 원문은 그대로입니다.',
  "'부족 이나'라는 원문은 그대로 보존합니다.",
  '서비스 은 자료를 제공하고 기준 가 다릅니다.',
  '가능한 만큼 알 수 있습니다. 비용은 부족하고 불명확으로 남습니다.'
];
for (const raw of preserved) test('preserve: ' + raw.slice(0, 60), () => assert.equal(korean.normalize(raw), raw));

test('existing reader-facing ID cleanup does not leave particle gaps', () => {
  const source = fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8');
  const fn = source.slice(source.indexOf('function displayText('), source.indexOf('function pendingQuestion('));
  const context = vm.createContext({PersonaKoreanText:korean});
  vm.runInContext(fn, context);
  const raw = '시간 효율성 (p1:r1) 을 위해 선택하나, 정보 (r2) 가 부족 이나 불명확 으로 남습니다.';
  const output = context.displayText(raw);
  assert.match(output, /효율성을/);
  assert.match(output, /정보가/);
  assert.match(output, /부족이나 불명확으로/);
  assert.equal(raw, '시간 효율성 (p1:r1) 을 위해 선택하나, 정보 (r2) 가 부족 이나 불명확 으로 남습니다.');
  // Optional script failure must not make the entire chat renderer fail.
  const fallback = vm.createContext({});
  vm.runInContext(fn, fallback);
  assert.equal(fallback.displayText('부족 이나'), '부족 이나');
});

test('browser export and existing script order', () => {
  const browser = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/korean-text.js'), 'utf8'), browser);
  assert.equal(browser.PersonaKoreanText.normalize('불명확 으로'), '불명확으로');
  const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf8');
  assert.ok(html.indexOf('/assets/korean-text.js') < html.indexOf('/assets/app.js'));
});

test('large input remains idempotent without altering facts or line breaks', () => {
  const raw = ('부족 이나 불명확 으로 19,900원; 할수 있습니다.\n'.repeat(2500));
  const fixed = korean.normalize(raw);
  assert.equal(korean.normalize(fixed), fixed);
  assert.equal(fixed.replace(/\s/g,''), raw.replace(/\s/g,''));
  assert.equal(fixed.split('\n').length, raw.split('\n').length);
});
