"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageFooterBar } from "@/components/PageFooterBar";
import { PersonaCard } from "@/components/PersonaCard";
import { IdeaSummary } from "@/components/IdeaSummary";
import { loadCustomTargets } from "@/components/TargetEditor";
import { runSessionAction, type Target } from "@/lib/soul-api";
import { cardTargetId, selectionPayload, targetPersonas } from "@/lib/persona-presentation";
import { useSoulSession } from "@/lib/use-soul-session";
const SECONDARY = "inline-flex h-11 shrink-0 items-center justify-center rounded-btn border border-btn-border bg-base px-4 text-sm text-ink-2 disabled:opacity-50";
const COUNT = ["", "한", "두", "세"];
export function TargetsClient() {
  const router = useRouter();
  const { session, loading, error: readError } = useSoulSession();
  const [pickedIds, setPickedIds] = useState<string[]>([]);
  const [custom, setCustom] = useState<Target[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialized = useRef<string | null>(null);
  useEffect(() => {
    if (!session || initialized.current === session.id) return;
    initialized.current = session.id;
    setCustom(loadCustomTargets(session.id));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Restore this session's external browser selection once.
    try { const saved = JSON.parse(localStorage.getItem(`soul.qwen.target-selection.v1:${session.id}`) ?? "[]"); if (Array.isArray(saved)) setPickedIds(saved.filter((id): id is string => typeof id === "string").slice(0, 3)); } catch {}
  }, [session]);
  if (loading) return <main className="p-20 text-ink-3" role="status">타깃을 불러오고 있어요.</main>;
  if (!session) return <main className="flex grow flex-col items-center justify-center gap-4 p-20"><h1 className="text-2xl font-semibold">먼저 아이디어를 적어주세요</h1>{readError && <p role="alert" className="text-conflict-fg">{readError}</p>}<Link href="/new" className={SECONDARY}>아이디어 적기</Link></main>;
  const sessionId = session.id;
  const canEdit = session.status === "CREATED" || session.status === "SELECTED";
  const targets = [...session.targets.filter(t => !custom.some(c => c.id === t.id)), ...custom];
  const personas = targetPersonas(session, targets);
  const picked = targets.filter(t => pickedIds.includes(t.id));
  const names = personas.filter(p => pickedIds.includes(p.id)).map(p => p.name).join(" · ");
  function toggle(id: string) {
    const next = pickedIds.includes(id) ? pickedIds.filter(value => value !== id) : picked.length < 3 ? [...pickedIds.filter(value => targets.some(t => t.id === value)), id] : pickedIds;
    setPickedIds(next);
    try { localStorage.setItem(`soul.qwen.target-selection.v1:${sessionId}`, JSON.stringify(next)); } catch {}
  }
  function edit(id: string) {
    const card = session?.cards.find(value => cardTargetId(session, value) === id);
    router.push(card ? `/targets/new?edit=${encodeURIComponent(card.id)}&from=compare` : `/targets/new?edit=${encodeURIComponent(id)}`);
  }
  async function select() {
    if (!picked.length || busy) return;
    const body = selectionPayload(picked, custom, personas);
    if (new Set(Object.values(body.display_names)).size !== picked.length) { setError("고른 페르소나의 이름을 서로 다르게 지정해 주세요."); return; }
    setBusy(true); setError(null);
    try { await runSessionAction(sessionId, "select", body); router.push("/compare"); }
    catch (err) { setError(err instanceof Error ? err.message : "페르소나를 준비하지 못했습니다."); }
    finally { setBusy(false); }
  }
  async function recommend() {
    setBusy(true); setError(null);
    try { await runSessionAction(sessionId, "targets/recommend"); setPickedIds([]); localStorage.removeItem(`soul.qwen.target-selection.v1:${sessionId}`); }
    catch (err) { setError(err instanceof Error ? err.message : "추천을 받지 못했습니다."); }
    finally { setBusy(false); }
  }
  return <>
    <main className="flex grow flex-col gap-5 px-[clamp(20px,6vw,80px)] pt-[30px] pb-6">
      <IdeaSummary input={session.input} />
      <div className="flex flex-wrap items-end gap-4"><div className="grow"><p className="font-mono text-xs tracking-[0.14em] text-muted">STEP 02</p><h1 className="mt-2 text-[28px] font-bold tracking-[-0.022em]">타깃 후보를 추천하고, 고칩니다</h1><p className="mt-2 text-[15px] leading-[1.7] text-ink-3">확정된 타깃이 아니라 후보예요. 최대 세 명을 고르면 페르소나를 만들고, 그 뒤 질문할 수 있어요.</p></div><button type="button" onClick={() => void recommend()} disabled={busy || session.status !== "CREATED" || session.cards.length > 0} className={SECONDARY}>다시 찾아보기</button>{session.cards.length > 0 && <Link href="/compare" className={SECONDARY}>고른 페르소나 보기</Link>}</div>
      {session.mode === "mock" && <p className="rounded-card bg-action-bg p-4 text-sm text-brand">모의 테스트 모드입니다. 실제 Qwen 결과가 아닙니다.</p>}
      {!canEdit && <p className="rounded-card bg-bubble p-4 text-sm text-ink-3">대화를 시작한 페르소나는 유지합니다. 다른 타깃은 새 아이디어에서 고를 수 있어요.</p>}
      {(error || readError) && <div role="alert" className="rounded-card bg-conflict-bg p-4 text-sm text-conflict-fg">{error || readError}</div>}
      {busy && <p role="status" className="rounded-card bg-action-bg p-4 text-sm text-brand">페르소나를 준비하고 있어요. 잠시만 기다려 주세요.</p>}
      <ul className="grid grid-cols-1 gap-[18px] md:grid-cols-2 xl:grid-cols-3">{personas.map(persona => <li key={persona.id} className="flex"><PersonaCard persona={persona} selected={pickedIds.includes(persona.id)} selectDisabled={busy || !canEdit || picked.length >= 3} onToggle={() => { if (!busy && canEdit) toggle(persona.id); }} onEdit={canEdit && !busy ? () => edit(persona.id) : undefined} readOnly={!canEdit || busy} /></li>)}{canEdit && <li className="flex"><div className="flex grow flex-col items-center justify-center gap-3 rounded-card border border-dashed border-btn-border bg-panel p-6"><span className="text-[28px] leading-none text-brand" aria-hidden="true">＋</span><h3 className="text-[15px] font-semibold">직접 만들기</h3><p className="text-center text-[13px] leading-[1.7] text-ink-3">이름과 이용자 유형, 겪는 상황을 직접 적어주세요.</p><Link href="/targets/new" aria-disabled={busy} tabIndex={busy ? -1 : undefined} className={`${SECONDARY} ${busy ? "pointer-events-none opacity-50" : ""}`}>만들러 가기</Link></div></li>}</ul>
    </main>
    <PageFooterBar title={picked.length ? `${names}, ${COUNT[picked.length]} 명 골랐어요` : "아직 고른 사람이 없어요"} description={busy ? "대화할 페르소나를 준비하고 있어요." : "한 명부터 세 명까지 함께 이야기할 수 있어요."}><button type="button" onClick={() => void select()} disabled={!picked.length || busy || !canEdit} className="h-12 shrink-0 rounded-btn bg-brand px-[26px] text-[15px] font-semibold text-white disabled:bg-bubble disabled:text-muted">{busy ? "준비 중…" : picked.length ? `이 ${COUNT[picked.length]} 명으로 진행하기` : "페르소나를 골라주세요"}</button></PageFooterBar>
  </>;
}
