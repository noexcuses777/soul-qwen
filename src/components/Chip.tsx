const TONE = {
  /** 중립 — 지금 쓰는 것, 기본 태그 */
  neutral: "bg-bubble text-ink-2",
  /** 충돌·주의 — 막히는 지점, 조건부 */
  conflict: "bg-conflict-bg text-conflict-fg",
  /** 합의·공통 — 찬성 */
  agree: "bg-agree-bg text-agree-fg",
  /** 다음 행동 — 링크, 제안 */
  action: "bg-action-bg text-action-fg border border-action-border",
  /** 반대 — 색상뿐 아니라 명도로도 구분한다 */
  solid: "bg-ink-2 text-white",
} as const;

export type ChipTone = keyof typeof TONE;

/**
 * 색만으로 의미를 전달하지 않는다. children 에 항상 글자 라벨이 들어간다.
 * mono=true 는 STEP·ROUND·판정 뱃지처럼 수치성 라벨에 쓴다.
 */
export function Chip({
  tone = "neutral",
  mono = false,
  children,
}: {
  tone?: ChipTone;
  mono?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-chip px-2.5 py-1 text-xs font-medium ${TONE[tone]} ${
        mono ? "font-mono font-semibold tracking-[0.1em]" : ""
      }`}
    >
      {children}
    </span>
  );
}
