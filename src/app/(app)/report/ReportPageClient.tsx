"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { api, runSessionAction, type SoulSession } from "@/lib/soul-api";
import { useSoulSession } from "@/lib/use-soul-session";
import { ReportClient, ReportDownloadButton } from "./ReportView";
import type { SoulReportView } from "./report-types";
import styles from "./report.module.css";
import { cardColor } from "@/lib/persona-presentation";

// React Strict Mode and two mounted views can request the same initial snapshot.
// Deduplicate the actual mutation; the backend also returns the cached revision.
const pendingFinish = new Map<string, Promise<SoulSession>>();
function finishOnce(id: string) {
  const existing = pendingFinish.get(id);
  if (existing) return existing;
  const promise = runSessionAction(id, "finish", {}).then(
    (session) => { pendingFinish.delete(id); return session; },
    (error: unknown) => { pendingFinish.delete(id); throw error; },
  );
  pendingFinish.set(id, promise);
  return promise;
}

function Waiting({ text }: { text: string }) {
  return <div role="status" className="rounded-card border border-card bg-base p-6"><div className="flex items-center gap-3"><span aria-hidden="true" className="size-5 animate-spin rounded-full border-2 border-line border-t-brand motion-reduce:animate-none" /><h1 className="text-xl font-semibold">{text}</h1></div><p className="mt-3 text-sm leading-relaxed text-muted">완료된 서버 응답을 기다리고 있습니다. Qwen의 비공개 사후 의견과 근거 연결을 정리하는 동안 시간이 걸릴 수 있습니다.</p></div>;
}

export function ReportPageClient() {
  const router = useRouter();
  const { session, loading: sessionLoading, error: sessionError, refresh } = useSoulSession();
  const [view, setView] = useState<SoulReportView | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadEpoch, setReloadEpoch] = useState(0);
  const autoAttempted = useRef<string | null>(null);
  const mounted = useRef(true);
  const sessionId = session?.id;
  const hasReport = Boolean(session?.report);
  const hasPublic = Boolean(session?.transcript.some((turn) => turn.phase !== "pre" && turn.phase !== "post"));
  const revision = session?.report_revision;
  const stale = session?.report_stale;
  const busy = Boolean(session?.pending_speaker || session?.pending_question);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    if (sessionLoading) return;
    if (!sessionId || !hasPublic) return;
    let active = true;
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      try {
        if (!hasReport) {
          const ongoing = pendingFinish.get(sessionId);
          if (ongoing) {
            setWorking(true);
            await ongoing;
          } else {
            if (busy || autoAttempted.current === sessionId) return;
            autoAttempted.current = sessionId;
            setWorking(true);
            await finishOnce(sessionId);
          }
        }
        const result = await api<SoulReportView>(`/sessions/${encodeURIComponent(sessionId)}/report-view`, undefined, controller.signal);
        if (active) { setView(result); setError(null); }
      } catch (err) {
        if (active && !controller.signal.aborted) setError(err instanceof Error ? err.message : "리포트를 불러오지 못했습니다.");
      } finally {
        if (active) { setLoading(false); setWorking(false); }
      }
    };
    void load();
    return () => { active = false; controller.abort(); };
  }, [sessionId, hasReport, hasPublic, revision, stale, busy, sessionLoading, reloadEpoch]);

  const regenerate = useCallback(async () => {
    if (!sessionId || working || busy) return;
    setWorking(true); setError(null);
    try {
      await finishOnce(sessionId);
      const next = await api<SoulReportView>(`/sessions/${encodeURIComponent(sessionId)}/report-view`);
      if (mounted.current) setView(next);
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "리포트를 생성하지 못했습니다.");
    } finally {
      if (mounted.current) { setWorking(false); setLoading(false); }
    }
  }, [sessionId, working, busy]);

  const newTargets = () => {
    if (!session) return;
    try { localStorage.setItem("soul.idea.draft.v2", JSON.stringify(session.input)); }
    catch { setError("아이디어 초안을 저장하지 못했습니다. 입력 화면에서 다시 입력해 주세요."); return; }
    router.push("/new");
  };
  const ask = (question: string, personaId: string | null) => {
    const search = new URLSearchParams({ ask: question });
    if (personaId) search.set("persona", personaId);
    router.push(`/chat?${search.toString()}`);
  };
  const displayError = error || sessionError;
  const currentView = hasPublic && view?.meta.session_id === sessionId ? view : null;
  const waiting = sessionLoading || (hasPublic && (loading || working));

  return <div className={`${styles.page} flex min-w-0 grow flex-col`}>
    <AppHeader current="05" right={currentView ? <ReportDownloadButton report={currentView} /> : undefined} />
    {displayError ? <div role="alert" className="mx-auto mt-5 w-[calc(100%-40px)] max-w-[1220px] rounded-card border border-card bg-conflict-bg p-4 text-sm leading-relaxed text-conflict-fg"><p>{displayError}</p><div className="mt-3 flex flex-wrap gap-3" data-report-controls><button type="button" onClick={() => { setError(null); void refresh().then(() => setReloadEpoch((value) => value + 1)); }} disabled={working} className="rounded-btn border border-btn-border bg-base px-3 py-2 disabled:opacity-50">서버 기록 다시 불러오기</button>{sessionId && hasPublic ? <button type="button" onClick={() => void regenerate()} disabled={working || busy} className="rounded-btn bg-brand px-3 py-2 text-white disabled:opacity-50">리포트 생성 다시 시도</button> : null}</div></div> : null}
    {currentView && session ? <ReportClient report={currentView} colors={Object.fromEntries(session.cards.map(card => [card.id, cardColor(session, card)]))} mode={session.mode} regenerating={working || busy} onRegenerate={() => void regenerate()} onContinue={() => router.push("/chat")} onAsk={ask} onNewTargets={newTargets} />
      : <main className={`${styles.body} grow`}>
        {waiting ? <Waiting text={working ? "대화를 정리하고 있어요" : "리포트 기록을 불러오고 있어요"} />
          : !session ? <section className="rounded-card border border-card bg-base p-6"><h1 className="text-2xl font-semibold">아직 분석할 대화가 없어요</h1><p className="mt-3 text-sm text-muted">아이디어를 입력하고 타깃을 정한 뒤 대화하면 리포트를 만들 수 있습니다.</p><Link href="/new" className="mt-5 inline-flex rounded-btn bg-brand px-5 py-3 text-sm font-semibold text-white">아이디어 입력하기</Link></section>
            : !hasPublic ? <section className="rounded-card border border-card bg-base p-6"><h1 className="text-2xl font-semibold">대화를 먼저 시작해 주세요</h1><p className="mt-3 text-sm text-muted">실제로 오간 발언을 근거로 리포트를 만듭니다. 공개 대화가 없으면 인사이트나 합의를 만들지 않습니다.</p><Link href={session.cards.length ? "/chat" : "/targets"} className="mt-5 inline-flex rounded-btn bg-brand px-5 py-3 text-sm font-semibold text-white">{session.cards.length ? "대화 시작하기" : "타깃 선택하기"}</Link></section>
              : <section className="rounded-card border border-card bg-base p-6"><h1 className="text-2xl font-semibold">{busy ? "대화가 진행 중이에요" : "리포트를 다시 만들 수 있어요"}</h1><p className="mt-3 text-sm text-muted">{busy ? "발언이 끝난 뒤 현재 대화로 리포트를 생성할 수 있습니다." : "오류 메시지를 확인한 뒤 다시 시도해 주세요. 기존 대화 기록은 보존됩니다."}</p><button type="button" onClick={() => void regenerate()} disabled={working || busy} className="mt-5 rounded-btn bg-brand px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">리포트 생성하기</button></section>}
      </main>}
  </div>;
}
