/**
 * 화면 가운데에 아이콘 · 제목 · 설명 · 버튼을 세로로 놓는 상태 화면 틀.
 * 06 빈 상태와 08 에러가 같은 뼈대를 쓴다.
 */
export function CenteredState({
  icon,
  title,
  description,
  actions,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  /** 제목 아래 버튼 줄 */
  actions: React.ReactNode;
  /** 버튼 아래 덧붙이는 블록 (06의 단계 안내, 08의 "남아 있는 것") */
  children?: React.ReactNode;
}) {
  return (
    <main className="flex grow flex-col items-center justify-center gap-7 px-20 py-16">
      {icon}
      <div className="flex flex-col items-center gap-2.5">
        <h1 className="text-[26px] font-bold tracking-[-0.02em]">{title}</h1>
        <p className="max-w-[520px] text-center text-[15px] leading-[1.7] text-ink-3">{description}</p>
      </div>
      <div className="flex items-center gap-2.5">{actions}</div>
      {children}
    </main>
  );
}

/** 상태 화면의 주 버튼·보조 버튼. 높이 48px로 터치 영역을 넉넉히 둔다. */
export const PRIMARY_BUTTON =
  "inline-flex h-12 shrink-0 items-center rounded-btn bg-brand px-[26px] text-[15px] font-semibold text-white hover:bg-brand-hover";
export const SECONDARY_BUTTON =
  "inline-flex h-12 shrink-0 items-center rounded-btn border border-btn-border bg-base px-5 text-[15px] text-ink-2";
