import { CenteredState } from "./CenteredState";

/** 08 에러 아이콘: 주의 틴트 원 + 느낌표. 색만이 아니라 제목 문장으로도 에러임을 알린다. */
export function ErrorIcon() {
  return (
    <span className="flex size-14 items-center justify-center rounded-full bg-conflict-bg">
      <svg
        width="26"
        height="26"
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--conflict-fg)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 8v5M12 17h.01" />
        <circle cx="12" cy="12" r="9" />
      </svg>
    </span>
  );
}

/**
 * 에러에서는 무엇이 남아 있는지 먼저 말하고, 거기까지로 진행할 선택지를 준다 (CLAUDE.md 9절).
 * remaining 이 없으면 "남아 있는 것" 줄을 그리지 않는다 — 없는 걸 있다고 말하지 않는다.
 */
export function ErrorState({
  title,
  description,
  actions,
  remaining,
}: {
  title: string;
  description: string;
  actions: React.ReactNode;
  /** 예: "ROUND 02 까지 · 발언 7개" */
  remaining?: string;
}) {
  return (
    <CenteredState icon={<ErrorIcon />} title={title} description={description} actions={actions}>
      {remaining && (
        <div className="mt-2 flex items-center gap-3.5 rounded-card border border-card bg-base px-5 py-4">
          <span className="font-mono text-[10px] font-semibold tracking-[0.12em] text-muted">남아 있는 것</span>
          <span className="text-sm text-ink-2">{remaining}</span>
        </div>
      )}
    </CenteredState>
  );
}

/** "ROUND 02 까지 · 발언 7개" — 남은 대화량을 계산해서 만든다. 하드코딩하면 데이터가 바뀔 때 거짓말을 한다. */
export function remainingLabel(round: number, utterances: number) {
  return `ROUND ${String(round).padStart(2, "0")} 까지 · 발언 ${utterances}개`;
}
