/** Source categories describe provenance, never probability or proof of a claim. */
const EVIDENCE_LABELS = [
  "AI 추론 · 고객 근거 미확인",
  "공개 시장 자료 참고",
  "제공된 고객·시장 자료 참고",
  "실제 인터뷰 자료 참고",
  "실제 행동 자료 참고",
] as const;

export function evidenceLabel(level: number): string {
  return (EVIDENCE_LABELS as readonly string[])[level] ?? "근거 유형 미확인";
}

export function evidenceDescription(level: number): string {
  if (level === 0) return "아이디어와 모델의 사전 지식에서 추론한 가설입니다. 실제 고객의 경험이나 행동으로 확인되지 않았습니다.";
  return `${evidenceLabel(level)}로 만든 가설입니다. 자료를 참고했다는 뜻이며, 이 해석이나 시장 수요가 입증됐다는 뜻은 아닙니다.`;
}

/** L0 on an uploaded source means uncategorized input, rather than an AI author. */
export function evidenceInputLabel(level: number): string {
  return level === 0 ? "자료 유형·수집 경로 미확인" : evidenceLabel(level).replace(/ 참고$/, "");
}
