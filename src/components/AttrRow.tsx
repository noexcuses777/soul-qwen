/** 라벨(mono) + 값 한 줄. 카드와 비교표에서 같은 모양으로 쓴다. */
export function AttrRow({
  label,
  children,
  labelWidth = "w-21",
  align = "baseline",
}: {
  label: string;
  children: React.ReactNode;
  labelWidth?: string;
  /** 값에 칩이 줄바꿈되며 들어가면 "start". 기본은 텍스트용 baseline. */
  align?: "baseline" | "start";
}) {
  const start = align === "start";
  return (
    <div className={`flex gap-2.5 ${start ? "items-start" : "items-baseline"}`}>
      <div
        className={`${labelWidth} shrink-0 font-mono text-[11px] tracking-[0.06em] text-muted ${
          start ? "pt-[5px]" : ""
        }`}
      >
        {label}
      </div>
      <div className="grow text-sm leading-relaxed">{children}</div>
    </div>
  );
}
