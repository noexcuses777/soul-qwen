"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { known, type IdeaInput } from "@/lib/soul-api";
export function IdeaSummary({ input, compact = false }: { input: IdeaInput; compact?: boolean }) {
  const router = useRouter();
  const [error, setError] = useState(false);
  function edit() {
    try { localStorage.setItem("soul.idea.draft.v2", JSON.stringify(input)); router.push("/new"); }
    catch { setError(true); }
  }
  return <section className="rounded-card border border-card bg-base px-6 py-[18px]" aria-label="작성한 아이디어">
    {compact ? <><div className="flex items-center gap-4"><div className="min-w-0 grow"><p className="mb-1 text-xs text-muted">내 아이디어</p><p className="text-sm font-medium leading-relaxed">{known(input.q1)}</p></div><button type="button" onClick={edit} className="h-10 shrink-0 rounded-btn border border-btn-border px-4 text-sm text-ink-2">고치기</button></div><details className="mt-3 text-sm"><summary className="cursor-pointer text-xs text-muted">아이디어 자세히 보기</summary><p className="mt-2 whitespace-pre-wrap leading-relaxed">{known(input.q3 || input.q3_1)}</p></details></> : <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-7"><h2 className="shrink-0 font-mono text-[11px] font-semibold tracking-[0.14em] text-muted">읽은 내용</h2><dl className="grid min-w-0 grow grid-cols-1 gap-4 text-sm sm:grid-cols-3 lg:gap-7"><div className="min-w-0"><dt className="text-xs text-muted">풀려는 문제</dt><dd className="mt-1 line-clamp-2 font-medium leading-relaxed" title={input.q3_1}>{known(input.q3_1)}</dd></div><div className="min-w-0"><dt className="text-xs text-muted">푸는 방법</dt><dd className="mt-1 line-clamp-2 font-medium leading-relaxed" title={input.q3 || input.q1}>{known(input.q3 || input.q1)}</dd></div><div className="min-w-0"><dt className="text-xs text-muted">겪을 사람</dt><dd className="mt-1 font-medium leading-relaxed">{input.customer_type && input.customer_type !== "아직 모르겠어요" ? input.customer_type : "대화할 타깃을 찾는 중"}</dd></div></dl><button type="button" onClick={edit} className="h-11 shrink-0 rounded-btn border border-btn-border px-4 text-sm text-ink-2">고칠래요</button></div>}
    {error && <p role="alert" className="mt-2 text-sm text-conflict-fg">브라우저에서 아이디어를 저장하지 못했습니다. 저장 설정을 확인해 주세요.</p>}
  </section>;
}
