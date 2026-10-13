"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TargetEditor, loadCustomTargets, saveCustomTargets, NEW_TARGET } from "@/components/TargetEditor";
import { PersonaEditor } from "@/components/PersonaEditor";
import { PersonaCard } from "@/components/PersonaCard";
import { targetPersonas } from "@/lib/persona-presentation";
import { useSoulSession } from "@/lib/use-soul-session";
import type { Target } from "@/lib/soul-api";
export function CreateTargetClient({ editId, returnTo = "/targets" }: { editId?: string; returnTo?: "/targets" | "/compare" }) {
  const router = useRouter();
  const { session, loading, error: readError } = useSoulSession();
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ sessionId: string; target: Target } | null>(null);
  if (loading) return <main className="p-20 text-ink-3" role="status">페르소나를 불러오고 있어요.</main>;
  if (!session) return <main className="p-20"><p>{readError ?? "먼저 아이디어를 적어주세요."}</p><Link href="/new" className="mt-4 inline-block text-brand">아이디어 적기</Link></main>;
  const card = returnTo === "/compare" ? session.cards.find(value => value.id === editId) : undefined;
  const custom = loadCustomTargets(session.id);
  const targets = [...session.targets.filter(t => !custom.some(c => c.id === t.id)), ...custom];
  const initial = targets.find(t => t.id === editId);
  const liveDraft = draft?.sessionId === session.id && draft.target.id === (initial?.id ?? "") ? draft.target : null;
  const preview = liveDraft ? targetPersonas(session, [...targets.filter(t => t.id !== liveDraft.id), { ...liveDraft, id: liveDraft.id || "custom-preview" }]).find(p => p.id === (liveDraft.id || "custom-preview")) : targetPersonas(session, targets).find(p => p.id === editId);
  const canEdit = session.status === "CREATED" || session.status === "SELECTED";
  if (!canEdit || (editId && !(returnTo === "/compare" ? card : initial))) return <main className="flex grow flex-col items-center justify-center gap-4 p-20"><p>지금 수정할 수 있는 페르소나를 찾지 못했어요.</p><Link href={returnTo} className="text-brand">목록으로 돌아가기</Link></main>;
  return <main className="flex grow flex-col gap-5 overflow-hidden px-[clamp(20px,6vw,80px)] pt-7 pb-6">
    <div className="flex flex-col gap-1.5"><Link href={returnTo} className="self-start font-mono text-[11px] tracking-[0.12em] text-muted">← {returnTo === "/compare" ? "한눈에 보기로 돌아가기" : "타깃 고르기로 돌아가기"}</Link><h1 className="text-[28px] font-bold leading-[1.38] tracking-[-0.022em]">{editId ? `${card?.presentation.display_name ?? preview?.name}님을 고쳐요` : "만나고 싶은 사람을 직접 만들어보세요"}</h1><p className="text-[15px] leading-[1.7] text-ink-3">{editId ? "알고 있는 조건에 맞게 고쳐요. 확인되지 않은 항목은 비워두세요." : "이름과 어떤 이용자인지, 겪는 상황을 적어주세요. 그 내용으로 대화할 페르소나를 준비해요."}</p></div>
    <div className="flex flex-wrap items-start gap-[26px]"><section className="w-full max-w-[800px] rounded-card border border-card bg-base px-[26px] py-[22px]">
      {card ? <PersonaEditor key={`${session.id}:${card.id}`} sessionId={session.id} initial={card} onCancel={() => router.push(returnTo)} onDone={() => router.push(returnTo)} /> : <TargetEditor key={`${session.id}:${editId ?? "new"}`} initial={initial ? { ...initial, display_name: preview?.name } : NEW_TARGET} onChange={target => setDraft({sessionId: session.id, target})} onCancel={() => router.push(returnTo)} onSave={target => {
        try { const saved = loadCustomTargets(session.id); saveCustomTargets(session.id, [...saved.filter(t => t.id !== target.id), target]); router.push(returnTo); }
        catch { setError("브라우저에서 페르소나를 저장하지 못했습니다."); }
      }} />}
      {error && <p role="alert" className="mt-4 text-sm text-conflict-fg">{error}</p>}
    </section>{preview && !card && <aside className="flex w-full max-w-sm"><PersonaCard persona={preview} readOnly /></aside>}</div>
  </main>;
}
