/**
 * 화면 하단 고정 바. 왼쪽에 지금 상태를, 오른쪽에 다음 단계 버튼을 둔다.
 * 01~05 화면이 같은 모양을 쓴다.
 */
export function PageFooterBar({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  /** 오른쪽 버튼 */
  children?: React.ReactNode;
}) {
  return (
    <footer className="flex h-20 shrink-0 items-center gap-5 border-t border-line bg-base px-20">
      <div className="flex grow flex-col gap-[3px]">
        <p className="text-[15px] font-semibold">{title}</p>
        {description && <p className="text-[13px] text-muted">{description}</p>}
      </div>
      {children}
    </footer>
  );
}
