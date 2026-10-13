import Link from "next/link";
import { Logo } from "@/components/AppHeader";

/**
 * SOUL entry point. Product claims match the local Qwen workflow.
 */
export default function LandingPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-[1440px] flex-col justify-center px-20">
      <div className="flex items-center gap-2.5">
        <Logo size={32} />
        <span className="text-xl font-semibold tracking-[-0.01em]">Soul</span>
      </div>

      <h1 className="mt-8 text-[52px] font-bold leading-[1.24] tracking-[-0.028em]">
        첫 고객 인터뷰 전에,
        <br />
        리허설부터.
      </h1>

      <p className="mt-6 max-w-[560px] text-[19px] leading-[1.72] text-ink-3">
        아이디어를 적으면 타깃 후보를 찾아주고, 그 타깃들이 한 방에 모여
        서로의 말을 들으며 답합니다. 인터뷰를 대신하지 않습니다. 앞뒤를 채웁니다.
      </p>

      <div className="mt-10 flex items-center gap-3">
        <Link
          href="/new"
          className="flex h-12 items-center rounded-btn bg-brand px-6 text-[15px] font-semibold text-white"
        >
          아이디어 적고 시작하기
        </Link>
        <Link
          href="/chat"
          className="flex h-12 items-center rounded-btn border border-btn-border px-6 text-[15px] text-ink-2"
        >
          저장한 대화 이어가기
        </Link>
      </div>

      <p className="mt-5 text-sm text-muted">
        로컬 Qwen · 최대 3인 페르소나 · 대화 근거가 있는 비교 리포트
      </p>
    </main>
  );
}
