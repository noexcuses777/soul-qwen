/**
 * "지금 무엇을 하는 중인지"를 단계로 보여주는 목록. 로딩을 스피너 하나로 때우지 않는다 (CLAUDE.md 9절).
 * 07 타깃 로딩과 07-2 리포트 로딩이 같은 모양을 쓴다.
 *
 * current 앞은 끝난 단계(체크), current 는 진행 중(파란 테두리), 뒤는 아직(회색 테두리).
 * 색만으로 구분하지 않도록 끝난 단계는 체크 아이콘, 진행 중은 글자 굵기로도 다르게 둔다.
 */
export function StepProgress({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex max-w-[420px] grow flex-col gap-3" aria-label="진행 단계">
      {steps.map((label, i) => {
        const state = i < current ? "done" : i === current ? "now" : "todo";
        return (
          <li
            key={label}
            className="flex items-center gap-[11px]"
            aria-current={state === "now" ? "step" : undefined}
          >
            {state === "done" ? (
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-green-deep">
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--bg-base)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </span>
            ) : (
              <span
                aria-hidden="true"
                className={`size-5 shrink-0 rounded-full ${
                  state === "now" ? "border-[3px] border-brand motion-safe:animate-pulse" : "border-2 border-input-border"
                }`}
              />
            )}
            <span
              className={`text-[15px] ${
                state === "now" ? "font-semibold text-ink" : state === "done" ? "text-ink-3" : "text-muted"
              }`}
            >
              {label}
              <span className="sr-only">{state === "done" ? " — 끝남" : state === "now" ? " — 진행 중" : " — 대기"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * 로딩 화면 상단 카드: 왼쪽에 STEP·제목·설명, 오른쪽에 단계 목록.
 */
export function ProgressPanel({
  step,
  title,
  description,
  steps,
  current,
}: {
  step: string;
  title: string;
  description: string;
  steps: string[];
  current: number;
}) {
  return (
    <section
      className="flex items-center gap-12 rounded-card border border-card bg-base px-7 py-[26px]"
      aria-live="polite"
    >
      <div className="flex flex-col gap-[7px]">
        <p className="font-mono text-xs font-medium tracking-[0.14em] text-muted">{step}</p>
        <h1 className="text-2xl font-bold tracking-[-0.018em]">{title}</h1>
        <p className="text-sm leading-[1.7] text-ink-3">{description}</p>
      </div>
      <StepProgress steps={steps} current={current} />
    </section>
  );
}
