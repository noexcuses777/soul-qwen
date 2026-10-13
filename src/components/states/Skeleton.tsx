/**
 * 형태가 정해진 화면(타깃 카드, 리포트)을 미리 보여주는 회색 막대.
 * 다 비워두면 무엇이 올지 모르니 모양을 먼저 보여준다 (CLAUDE.md 9절).
 * 스크린 리더에는 읽히지 않게 숨기고, 진행 상황은 ProgressPanel 이 알린다.
 */
export function Bar({
  className = "",
  round = false,
}: {
  /** 크기는 Tailwind 로 넘긴다: "h-3 w-full", "h-[22px] w-[76px]" */
  className?: string;
  round?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className={`block bg-th motion-safe:animate-pulse ${round ? "rounded-full" : "rounded-md"} ${className}`}
    />
  );
}

/** 02 타깃 카드 모양의 스켈레톤 (07 타깃 로딩) */
export function PersonaCardSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-3.5 rounded-card border border-card bg-base px-5 py-[18px]">
      <div className="flex items-center gap-[11px]">
        <Bar round className="size-[38px] shrink-0" />
        <div className="flex grow flex-col gap-1.5">
          <Bar className="h-3.5 w-[88px]" />
          <Bar className="h-2.5 w-[140px]" />
        </div>
      </div>
      <div className="flex flex-col gap-[7px]">
        <Bar className="h-3 w-full" />
        <Bar className="h-3 w-full" />
        <Bar className="h-3 w-[72%]" />
      </div>
      <div className="h-px bg-divider" />
      <div className="flex gap-1.5">
        <Bar className="h-[22px] w-[76px]" />
        <Bar className="h-[22px] w-[92px]" />
        <Bar className="h-[22px] w-16" />
      </div>
      <div className="flex gap-1.5">
        <Bar className="h-[22px] w-[104px]" />
        <Bar className="h-[22px] w-[84px]" />
      </div>
    </div>
  );
}

/** 05 리포트 모양의 스켈레톤 (07-2 리포트 로딩): 숫자 4칸 + 쟁점 블록 + 문단 블록 */
export function ReportSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-6">
      <div className="flex gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex flex-1 flex-col gap-2.5 rounded-card border border-card bg-base px-[18px] py-4">
            <Bar className="h-2.5 w-[72px]" />
            <Bar className="h-[22px] w-10" />
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-4 rounded-card border border-card bg-base px-[26px] py-[22px]">
        <div className="flex items-center gap-3">
          <Bar className="h-3 w-7" />
          <Bar className="h-4 w-[300px]" />
        </div>
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Bar round className="size-[26px] shrink-0" />
              <Bar className="h-3 w-[62px]" />
              <Bar className="h-[22px] w-[70px]" />
              <Bar className="h-3 w-[54%]" />
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-2 rounded-[11px] bg-panel px-4 py-[13px]">
          <Bar className="h-3 w-full" />
          <Bar className="h-3 w-[68%]" />
        </div>
      </div>

      <div className="flex flex-col gap-3.5 rounded-card border border-card bg-base px-[26px] py-[22px]">
        <div className="flex items-center gap-3">
          <Bar className="h-3 w-7" />
          <Bar className="h-4 w-[260px]" />
        </div>
        <div className="flex flex-col gap-2.5">
          <Bar className="h-3 w-full" />
          <Bar className="h-3 w-full" />
          <Bar className="h-3 w-[44%]" />
        </div>
      </div>
    </div>
  );
}
