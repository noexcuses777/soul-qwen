import type { Metadata } from "next";
import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

export const metadata: Metadata = { title: "상태 화면 모음" };

/**
 * 빈 상태 · 로딩 · 에러를 한곳에서 열어보는 목록.
 * 화면 사이 데이터가 아직 안 넘어가서(HANDOFF.md 2절), 04·05를 붙이기 전까지는
 * 실제 흐름에서 이 상태들이 뜨지 않는다. 그때까지 여기서 확인한다.
 */
const STATES = [
  { href: "/states/empty", no: "06", title: "빈 상태", body: "적어둔 아이디어가 없을 때" },
  { href: "/states/error", no: "08", title: "에러", body: "대화 중 연결이 끊겼을 때 — 남은 것과 선택지" },
  { href: "/states/loading-targets", no: "07", title: "로딩 — 타깃", body: "01 → 02 사이, 타깃 후보 찾는 중" },
  { href: "/states/loading-chat", no: "07-1", title: "로딩 — 발화 대기", body: "페르소나가 순차로 답하는 중" },
  { href: "/states/loading-report", no: "07-2", title: "로딩 — 리포트", body: "대화를 쟁점별로 정리하는 중" },
];

export default function Page() {
  return (
    <>
      <AppHeader />
      <main className="flex grow flex-col gap-6 px-20 py-9">
        <div className="flex flex-col gap-2">
          <p className="font-mono text-xs font-medium tracking-[0.14em] text-muted">STATES</p>
          <h1 className="text-[28px] font-bold leading-[1.38] tracking-[-0.022em]">상태 화면 모음</h1>
          <p className="text-[15px] leading-[1.7] text-ink-3">
            실제 저장한 세션의 상태 화면으로 이동합니다. 진행 상황과 오류는 해당 화면에서 확인할 수 있어요.
          </p>
        </div>
        <ul className="grid grid-cols-2 gap-4">
          {STATES.map((s) => (
            <li key={s.href}>
              <Link
                href={s.href}
                className="flex min-h-11 flex-col gap-1.5 rounded-card border border-card bg-base px-6 py-5 hover:border-btn-border"
              >
                <span className="font-mono text-[11px] font-semibold tracking-[0.12em] text-brand">{s.no}</span>
                <span className="text-[15px] font-semibold">{s.title}</span>
                <span className="text-[13px] leading-[1.6] text-muted">{s.body}</span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
