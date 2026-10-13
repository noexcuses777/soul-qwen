/** 제품 화면 공통 레이아웃. 헤더는 각 화면에서 현재 단계를 넘겨 직접 렌더한다. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-dvh flex-col bg-alt">{children}</div>;
}
