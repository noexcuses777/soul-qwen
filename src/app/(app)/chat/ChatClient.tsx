"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { ChatComposer, ChatRoomHeader, PersonaMessage, QuestionChips, TypingMessage, UserMessage } from "@/components/chat/ChatParts";
import { currentSessionId, getSession, rememberSession, runSessionAction, type NextQuestionRecommendation, type SoulSession } from "@/lib/soul-api";
import { useSoulSession } from "@/lib/use-soul-session";
import { cardColor } from "@/lib/persona-presentation";
import { IdeaSummary } from "@/components/IdeaSummary";
import { displayChatText } from "@/lib/chat-presentation";
import { canFillQuestionDraft, loadNextQuestion, sameQuestionContext, type QuestionRequestContext } from "@/lib/next-question";
import { DmPanel } from "./DmPanel";
type Ask = { question: string; persona_id: string | null; interaction: "auto" | "direct" };
const SECONDARY = "inline-flex h-11 items-center justify-center rounded-btn border border-btn-border bg-base px-4 text-sm text-ink-2 disabled:opacity-50";
const pendingKey = (id: string) => `soul.qwen.pending-message.v1:${id}`;

export function ChatClient({ initialDraft = "", initialPersona = "" }: { initialDraft?: string; initialPersona?: string }) {
  const router = useRouter();
  const { session, loading, error: readError } = useSoulSession();
  const [draft, setDraft] = useState(initialDraft);
  const [targetId, setTargetId] = useState(initialPersona);
  const [dmId, setDmId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [questionAt, setQuestionAt] = useState(0);
  const [retry, setRetry] = useState<Ask | null>(null);
  const [nextQuestion, setNextQuestion] = useState<{ context: QuestionRequestContext; recommendation: NextQuestionRecommendation; draftPreserved: boolean } | null>(null);
  const [nextQuestionError, setNextQuestionError] = useState<{ sessionId: string; threadId: string; message: string } | null>(null);
  const draftVersion = useRef(0);
  const targetVersion = useRef(0);
  const latestSession = useRef(session);
  const nextQuestionRequest = useRef<AbortController | null>(null);
  const offeredQuestionIds = useRef(new Set<string>());
  const scrollRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const initialized = useRef<string | null>(null);
  useEffect(() => { latestSession.current = session; }, [session]);
  useEffect(() => () => { nextQuestionRequest.current?.abort(); }, []);
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [session?.transcript.length, session?.pending_speaker]);
  useEffect(() => {
    if (!session || initialized.current === session.id) return;
    initialized.current = session.id;
    const pending = session.dialogue_runtime.followup;
    if (pending && !pending.done) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Restore a persisted server mutation for explicit retry.
      setRetry({ question: pending.key[0], persona_id: pending.key[1], interaction: pending.key[2] === "direct" ? "direct" : "auto" });
    } else if (session.error) {
      try { const raw = localStorage.getItem(pendingKey(session.id)); if (raw) setRetry(JSON.parse(raw)); } catch {}
    }
  }, [session]);
  const unfinished = !!session?.dialogue_runtime.followup && !session.dialogue_runtime.followup.done;
  const live = unfinished && !session?.error;
  const sessionId = session?.id;
  useEffect(() => {
    if (!sessionId || !live || busy) return;
    let reading = false;
    let active = true;
    const timer = setInterval(async () => { if (reading) return; reading = true; try { const latest = await getSession(sessionId); if (active && (currentSessionId() === sessionId || currentSessionId() === null)) rememberSession(latest); } catch {} finally { reading = false; } }, 1500);
    return () => { active = false; clearInterval(timer); };
  }, [sessionId, live, busy]);
  const personas = (session?.cards ?? []).map(card => ({ id: card.id, name: card.presentation.display_name, segment: card.immutable_core.identity_context.segment, color: cardColor(session!, card) }));
  const byId = (id?: string | null) => personas.find(p => p.id === id);
  const publicTurns = (session?.transcript ?? []).filter(t => t.phase === "group");
  const utteranceOwners = Object.fromEntries(publicTurns.map(turn => [turn.id, byId(turn.persona_id)?.name ?? ""]));
  const inProgress = busy || live;
  const pendingSpeaker = byId(session?.pending_speaker);
  const dmPersona = byId(dmId);
  const reported = !!session?.report;
  const reportPending = !!session?.dialogue_runtime.report_snapshot && !session.dialogue_runtime.report_snapshot.done;
  const completedThread = session?.threads.at(-1);
  const activeRecommendation = nextQuestion?.context.sessionId === session?.id && nextQuestion?.context.threadId === completedThread?.id && nextQuestion?.context.transcriptLength === session?.transcript.length ? nextQuestion : null;
  const recommendationError = nextQuestionError && nextQuestionError.sessionId === session?.id && nextQuestionError.threadId === completedThread?.id ? nextQuestionError.message : null;
  const recoverableMessage = unfinished || ((session?.status === "PRE" || session?.status === "FAILED") && !publicTurns.length);

  function updateDraft(value: string) { draftVersion.current += 1; setDraft(value); }
  function updateTarget(value: string) { targetVersion.current += 1; setTargetId(value); }
  function questionContext(current: SoulSession): QuestionRequestContext {
    return { sessionId: current.id, threadId: current.threads.at(-1)?.id ?? "", transcriptLength: current.transcript.length, publicRevision: current.transcript.filter(turn => turn.phase === "group").length, draftVersion: draftVersion.current, targetVersion: targetVersion.current };
  }
  async function reviewNextQuestion() {
    if (!session || !completedThread || inProgress || unfinished || reportPending || nextQuestionRequest.current) return;
    const requested = questionContext(session);
    const controller = new AbortController();
    nextQuestionRequest.current = controller;
    setBusy(true); setOperation("next-question"); setNextQuestionError(null);
    try {
      const recommendation = await loadNextQuestion(session.id, requested.publicRevision, controller.signal);
      const current = latestSession.current;
      if (controller.signal.aborted || !current || !sameQuestionContext(requested, questionContext(current), currentSessionId())) return;
      if (recommendation.revision !== requested.publicRevision) throw new Error("대화가 바뀌었습니다. 현재 대화를 기준으로 다시 검토해 주세요.");
      const recommendationKey = `${requested.sessionId}:${recommendation.id}`;
      const fillDraft = recommendation.status === "discussion" && !offeredQuestionIds.current.has(recommendationKey) && canFillQuestionDraft(requested, questionContext(current), currentSessionId());
      offeredQuestionIds.current.add(recommendationKey);
      setNextQuestion({ context: requested, recommendation, draftPreserved: recommendation.status === "discussion" && !fillDraft });
      if (fillDraft) { updateDraft(recommendation.question); updateTarget(""); }
    } catch (err) {
      const current = latestSession.current;
      if (!controller.signal.aborted && current && sameQuestionContext(requested, questionContext(current), currentSessionId())) setNextQuestionError({ sessionId: requested.sessionId, threadId: requested.threadId, message: err instanceof Error ? err.message : "다음 질문을 검토하지 못했습니다." });
    } finally {
      if (nextQuestionRequest.current === controller) { nextQuestionRequest.current = null; setBusy(false); setOperation(""); }
    }
  }

  async function send(text: string, directedPersona?: string | null, resume = false) {
    if (!session || inProgress || !text.trim() || text.trim().length > 500) return;
    const mention = text.trim().match(/^@(\S+)/)?.[1];
    const mentioned = mention ? personas.find(p => p.name === mention) : null;
    const addressed = directedPersona || targetId || mentioned?.id || null;
    const request: Ask = resume && retry ? retry : { question: text.trim(), persona_id: addressed, interaction: addressed ? "direct" : "auto" };
    setBusy(true); setOperation("ask"); setError(null); setRetry(request);
    try { localStorage.setItem(pendingKey(session.id), JSON.stringify(request)); } catch {}
    try {
      await runSessionAction(session.id, "ask", request);
      setRetry(null); updateDraft("");
      try { localStorage.removeItem(pendingKey(session.id)); } catch {}
    } catch (err) { setError(err instanceof Error ? err.message : "대화를 이어가지 못했습니다."); }
    finally { setBusy(false); setOperation(""); }
  }
  async function suggestions() {
    if (!session || inProgress) return;
    if (session.suggestions.length) { setQuestionAt(value => value + 2); return; }
    setBusy(true); setOperation("suggestions"); setError(null);
    try { await runSessionAction(session.id, "suggestions"); }
    catch (err) { setError(err instanceof Error ? err.message : "질문 추천을 받지 못했습니다."); }
    finally { setBusy(false); setOperation(""); }
  }
  async function finish() {
    if (!session || inProgress || unfinished || !publicTurns.length) return;
    setBusy(true); setOperation("finish"); setError(null);
    try { await runSessionAction(session.id, "finish"); router.push("/report"); }
    catch (err) { setError(err instanceof Error ? err.message : "리포트를 만들지 못했습니다."); }
    finally { setBusy(false); setOperation(""); }
  }
  const questions = session?.suggestions.length ? [0, 1].map(offset => session.suggestions[(questionAt + offset) % session.suggestions.length].question) : [];
  if (loading) return <main className="flex grow items-center justify-center p-20" role="status">저장한 대화를 불러오고 있어요.</main>;
  if (!session?.cards.length) return <main className="flex grow flex-col items-center justify-center gap-4 p-20"><h1 className="text-2xl font-semibold">먼저 페르소나를 만들어 주세요</h1>{readError && <p role="alert" className="text-conflict-fg">{readError}</p>}<Link href="/targets" className={SECONDARY}>이용자 고르기</Link></main>;

  function eventsBefore(index: number, current: SoulSession) { return current.chat_events.filter(event => event.before === index && (current.lounge_mode !== "guided" || event.role === "founder")); }
  return <>
    <AppHeader current="04" right={<div className="flex gap-2">{reported && <Link href="/report" className={SECONDARY}>{session.report_stale ? "이전 리포트 보기" : "리포트 보기"}</Link>}<button type="button" disabled={inProgress || unfinished || !publicTurns.length} onClick={() => void finish()} className="h-11 rounded-btn bg-brand px-[18px] text-sm font-semibold text-white disabled:opacity-50">{operation === "finish" ? "리포트 생성 중…" : session.report_stale ? "리포트 업데이트" : "리포트 만들기"}</button></div>}/>
    <div ref={scrollRef} onScroll={event => { const el = event.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 90; }} className="flex min-h-0 grow flex-col items-center overflow-y-auto px-5 py-6">
      <div className="flex w-full max-w-[880px] flex-col gap-4" aria-live="polite" aria-busy={inProgress}><IdeaSummary input={session.input} compact /><ChatRoomHeader personas={personas} round={session.threads.length} interaction={operation === "ask" && retry ? retry.interaction : session.dialogue_runtime.followup?.key[2] ?? (targetId ? "direct" : "auto")} onOpenDm={id => { if (!inProgress && !unfinished) setDmId(id); }}/>
        <p className="text-xs leading-relaxed text-muted">{session.mode === "mock" ? "모의 테스트 모드입니다. 실제 Qwen 성능 평가 결과가 아닙니다." : "가상 페르소나와의 대화입니다."}</p>
        {!publicTurns.length && !inProgress && <div className="rounded-card border border-card bg-base p-6"><h2 className="text-lg font-semibold">궁금한 점을 물어보세요</h2><p className="mt-2 text-sm leading-relaxed text-ink-3">선택한 {personas.length}명이 먼저 자기 조건에서 답하고, 서로의 말에 적용되는 조건이나 차이를 비교합니다. 답변이 끝난 뒤에도 아래 입력칸에서 계속 질문할 수 있어요.</p></div>}
        {session.transcript.map((turn, index) => { const p = byId(turn.persona_id); const parent = publicTurns.find(t => t.id === turn.reply_to); const parentPersona = byId(parent?.persona_id); return <Fragment key={turn.id}>{eventsBefore(index, session).map((event, i) => event.role === "founder" ? <UserMessage key={`${index}-${i}`}>{event.content}</UserMessage> : <p key={`${index}-${i}`} className="self-center rounded-full bg-bubble px-4 py-2 text-center text-xs leading-relaxed text-ink-3">{event.content}</p>)}{turn.phase === "group" && p && <div id={`utterance-${turn.id}`} data-utterance-id={turn.id}>{parent && <p className="mb-1 ml-[51px] text-xs text-muted">↳ {parentPersona?.name}님에게 답함</p>}<PersonaMessage name={p.name} segment={p.segment} color={p.color}>{displayChatText(turn.content, p.id, personas, utteranceOwners)}</PersonaMessage></div>}</Fragment>; })}
        {eventsBefore(session.transcript.length, session).map((event, i) => event.role === "founder" ? <UserMessage key={`tail-${i}`}>{event.content}</UserMessage> : <p key={`tail-${i}`} className="self-center rounded-full bg-bubble px-4 py-2 text-center text-xs leading-relaxed text-ink-3">{event.content}</p>)}
        {!inProgress && !unfinished && completedThread?.status === "returned_to_user" && <div className="rounded-card border border-line bg-base px-4 py-3 text-sm leading-relaxed text-ink-3">
          <p>{completedThread.stop_reason === "response_budget" ? "이번 질문의 대화 분량에 도달했어요. 남은 쟁점은 이어서 살펴볼 수 있어요." : completedThread.stop_reason === "no_grounded_expansion" || completedThread.stop_reason === "real_world_checks_remaining" || completedThread.stop_reason === "repetition_or_unsupported" ? "추가 판단에는 실제 자료나 더 구체적인 조건이 필요해요." : completedThread.stop_reason === "direct" ? "지정한 사람의 답변입니다. 모두의 관점을 비교하려면 질문 대상을 ‘모두’로 바꿔 주세요." : "이번 질문에 대한 비교를 마쳤어요. 같은 입력칸에서 쟁점을 더 살펴볼 수 있어요."}</p>
          {completedThread.remaining_issues.length > 0 && <p className="mt-1 text-xs text-muted">확인할 점: {completedThread.remaining_issues.slice(0, 2).join(' · ')}</p>}
          {activeRecommendation && <div className="mt-3 border-t border-line pt-3" role="status">
            <p className="font-medium text-ink-2">{activeRecommendation.recommendation.status === "discussion" ? "다음 질문을 제안한 이유" : activeRecommendation.recommendation.status === "needs_evidence" ? activeRecommendation.recommendation.question ? "실제 고객에게 확인할 질문" : "실제 자료가 필요한 부분" : "현재 대화에서 새로 확장할 질문을 찾지 못했어요."}</p>
            <p className="mt-1">{activeRecommendation.recommendation.why}</p>
            {activeRecommendation.recommendation.missing_information.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5">{activeRecommendation.recommendation.missing_information.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}
            {activeRecommendation.recommendation.question && <p className="mt-2 whitespace-pre-wrap rounded-[10px] bg-bubble px-3 py-2 text-ink-2">{activeRecommendation.recommendation.question}</p>}
            {activeRecommendation.recommendation.status === "discussion" && <p className="mt-2 text-xs text-muted">{activeRecommendation.draftPreserved ? "작성 중인 질문을 유지했어요. 위 제안을 참고해 입력칸에서 이어서 질문하세요." : "질문을 아래 입력칸에 넣었어요. 내용을 확인하거나 수정한 뒤 보내세요."}</p>}
            {activeRecommendation.recommendation.status === "needs_evidence" && <p className="mt-2 text-xs text-muted">고객 인터뷰나 운영 자료로 확인할 내용입니다. 자료나 구체적인 조건을 확보한 뒤 아래 입력칸에서 이어가세요.</p>}
            {activeRecommendation.recommendation.status === "no_new_question" && <p className="mt-2 text-xs text-muted">새로운 조건을 직접 입력하거나 대화를 리포트로 정리할 수 있어요.</p>}
            {activeRecommendation.recommendation.source_utterance_ids.length > 0 && <div className="mt-2 flex flex-wrap gap-3 text-xs">{activeRecommendation.recommendation.source_utterance_ids.filter(id => utteranceOwners[id]).map((id, index) => <a key={id} href={`#utterance-${id}`} className="text-brand underline">{utteranceOwners[id]}님 관련 발언{index > 0 ? ` ${index + 1}` : ""}</a>)}</div>}
          </div>}
          {recommendationError && <p className="mt-2 text-sm text-conflict-fg" role="alert">질문 검토를 완료하지 못했습니다: {recommendationError}</p>}
          {!activeRecommendation && <button type="button" disabled={reportPending} onClick={() => void reviewNextQuestion()} className="mt-2 text-sm font-medium text-brand disabled:opacity-50">이 쟁점 더 살펴보기</button>}
        </div>}
        {inProgress && <div role="status" className="rounded-card bg-bubble px-4 py-3 text-sm text-ink-3">{operation === "next-question" ? "이미 묻고 답한 내용과 남은 조건을 살펴 다음 질문이 필요한지 검토하고 있어요." : operation === "suggestions" ? "이 아이디어와 페르소나에 맞는 질문을 추천하고 있어요." : operation === "finish" ? "대화를 리포트로 정리하고 있어요." : session.status === "PRE" ? "각자 첫 답변을 준비하고 있어요." : "각자의 답과 서로의 조건을 비교하며 대화하고 있어요."}</div>}
        {inProgress && pendingSpeaker && session.status !== "PRE" && operation !== "finish" && operation !== "next-question" && <TypingMessage name={pendingSpeaker.name} color={pendingSpeaker.color}/>}
        {(error || session.error || readError) && <div role="alert" className="rounded-card bg-conflict-bg p-4 text-sm leading-relaxed text-conflict-fg"><p>진행하지 못했습니다: {error || session.error || readError}</p><p className="mt-2">완료된 발언은 저장되어 있어요. 같은 메시지를 재개하면 중단된 지점부터 이어갑니다.</p>{retry && recoverableMessage && <button type="button" onClick={() => void send(retry.question, retry.persona_id, true)} disabled={inProgress} className={`${SECONDARY} mt-3`}>중단된 메시지 재개</button>}{session.dialogue_runtime.report_snapshot && !session.dialogue_runtime.report_snapshot.done && <button type="button" onClick={() => void finish()} disabled={inProgress} className={`${SECONDARY} mt-3`}>리포트 생성 재개</button>}</div>}

      </div>
    </div>
    <div className="flex shrink-0 justify-center border-t border-line bg-alt px-5 pt-3 pb-5"><div className="flex w-full max-w-[880px] flex-col gap-2"><div className="flex flex-wrap items-center gap-3">{questions.length ? <QuestionChips questions={questions} onPick={question => { updateDraft(question); updateTarget(""); }} onMore={() => setQuestionAt(value => value + 2)}/> : <button type="button" disabled={inProgress} onClick={() => void suggestions()} className={SECONDARY}>질문 추천받기</button>}<label className="ml-auto flex items-center gap-2 text-xs text-muted">질문할 대상<select value={targetId} disabled={inProgress || unfinished || reportPending} onChange={event => updateTarget(event.target.value)} className="h-9 rounded-[9px] border border-input-border bg-base px-2 text-ink-2"><option value="">모두 · 상호 대화</option>{personas.map(p => <option key={p.id} value={p.id}>{p.name} · 지정 답변</option>)}</select></label></div><ChatComposer value={draft} onChange={updateDraft} onSend={() => void send(draft)} sending={inProgress || unfinished || reportPending} placeholder="궁금한 점을 물어보세요. 같은 입력칸에서 계속 대화할 수 있어요."/><span className="self-end text-xs text-muted">{draft.length} / 500자</span></div></div>
    {dmPersona && <DmPanel persona={dmPersona} session={session} sending={inProgress} onSend={question => void send(question, dmPersona.id)} onClose={() => setDmId(null)}/>}
  </>;
}
