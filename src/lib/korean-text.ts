  // Formatting generated prose, not a morphological parser. Restrict ambiguous
  // one-letter particles to these nominal terms; never join arbitrary words.
  const nouns = [
    '불명확', '불확실', '불확실성', '부족', '미확인', '가능성', '신뢰도', '신뢰',
    '검증', '효과', '효율성', '정보', '데이터', '조건', '비용', '예산', '전환',
    '대안', '기준', '가설', '의견', '도입', '판단', '선택', '근거', '시간',
    '기능', '결과', '경험', '문제', '서비스', '사용자', '타깃', '단계', '개인',
    '기관', '인터뷰', '프로그램', '범위', '한계', '관점', '도구', '품질',
    '시장', '요구', '장벽', '목표', '가치', '분석', '정확도', '반응', '추천'
  ].sort((a, b) => b.length - a.length).join('|');
  const space = '[ \\t\\u00a0]+';
  const end = '(?=$|[^\\p{L}\\p{N}_])';
  const bound = '(?<![\\p{L}\\p{N}_])';
  const longParticles = [
    '으로부터', '으로서는', '으로서', '으로써', '으로는', '으로도', '으로만',
    '으로', '에게서는', '에게서', '에게는', '에게도', '에게', '에서부터',
    '에서는', '에서도', '에서만', '에서', '에는', '에도', '에만',
    '이나마', '이나', '이라고는', '이라고', '이라는', '이란', '이라면',
    '이든지', '이든', '부터는', '부터', '까지는', '까지', '처럼'
  ].sort((a, b) => b.length - a.length).join('|');
  const spacedLong = new RegExp(bound + '([가-힣]+)' + space + '(' + longParticles + ')' + end, 'gu');
  const spacedShort = new RegExp(bound + '(' + nouns + ')' + space + '(은|는|을|를|이|가|과|와|도|만|의|에)' + end, 'gu');
  // Actual Qwen smoke also emitted "PoC 를". Known product/research terms
  // can take Korean particles; preserve unknown identifiers and model names.
  const spacedTerm = new RegExp(bound + '(PoC|MVP|SaaS|B2B|B2C|AI|LLM|Qwen|UNKNOWN|NSona|nsona)' + space + '(' + longParticles + '|은|는|을|를|이|가|과|와|도|만|의|에|로)' + end, 'gu');
  // These independent-noun phrases are unambiguous in the listed conjugations.
  // Do not globally attach 만큼/뿐/대로, or replace ambiguous 되/돼 and 안/않.
  const canPhrase = /(?<![\p{L}\p{N}_])((?:[가-힣]+)?(?:할|될|볼|알|있을|없을|바뀔|줄))[ \t\u00a0]*수[ \t\u00a0]*(있습니다|있어요|있다|있는|있으면|없습니다|없어요|없다|없는|없으면)(?=$|[^\p{L}\p{N}_])/gu;
  // Preserve literal quotes and identifiers byte for byte. No external service
  // receives text, and this formatter never edits the saved session or evidence.
  const protectedText = /(```[\s\S]*?(?:```|$)|`[^`\r\n]*`|https?:\/\/[^\s<>]+|"[^"\r\n]*"|'[^'\r\n]*'|“[^”\r\n]*”|‘[^’\r\n]*’)/g;

  function joinShort(match: string, noun: string, particle: string, offset: number, prose: string) {
    // 이 can also be a demonstrative: "정보 이 부분", "검증 이 후".
    // Do not turn that ambiguity into a different sentence structure.
    if (particle === '이' && /^[ \t\u00a0]+(?:후|전|때|부분|경우|조건|문제|기준|단계|정보|내용|결과|서비스|도구|사람|분|범위)(?=$|[^\p{L}\p{N}_])/u.test(prose.slice(offset + match.length))) return match;
    const hasFinal = (noun.charCodeAt(noun.length - 1) - 0xac00) % 28 !== 0;
    // If the allomorph is also wrong, leave it for generation-time proofreading;
    // this layer changes only whitespace, never words or their particles.
    if (['은', '을', '이', '과'].includes(particle) && !hasFinal) return match;
    if (['는', '를', '가', '와'].includes(particle) && hasFinal) return match;
    return noun + particle;
  }

  export function normalize(text: string): string {
    if (typeof text !== 'string' || !text) return text;
    return text.split(protectedText).map((part, index) => index % 2 ? part : part
      .replace(spacedLong, '$1$2')
      .replace(spacedShort, joinShort)
      .replace(spacedTerm, '$1$2')
      .replace(canPhrase, '$1 수 $2')).join('');
  }

