"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { api, createSession, DEFAULT_LIMITS, type Evidence, type IdeaInput, type InputLimits } from "@/lib/soul-api";

import { evidenceInputLabel } from "@/lib/evidence-presentation";

export const DRAFT_KEY = "soul.idea.draft.v2";
const EMPTY: IdeaInput = { q1: "", q2: "", q3: "", q3_1: "", q3_2: "", q4_1: "", q5: "IT", customer_type: "아직 모르겠어요", founder_strength: "", evidence: [] };
const FIELDS = ["IT", "교육", "금융", "운영관리", "네트워킹", "농업/축산업", "라이프스타일", "모빌리티", "마케팅/PR", "미디어/엔터테인먼트", "바이오/의료", "에너지/자원", "유통/물류", "임팩트", "재무", "프롭테크", "하드웨어", "기타", "패션", "F&B", "뷰티", "생활"];
const CUSTOMERS: IdeaInput["customer_type"][] = ["개인 고객에게 팝니다", "기업·기관에 팝니다", "아직 모르겠어요"];
const CARD = "flex flex-col gap-[18px] rounded-card border border-card bg-base px-[26px] py-6";
const AREA = "w-full resize-none rounded-[11px] border border-input-border bg-input px-3.5 py-3 text-[15px] leading-[1.7]";
const INPUT = "h-11 w-full rounded-[11px] border border-input-border bg-input px-3.5 text-[15px]";
const SECONDARY = "inline-flex min-h-11 items-center gap-[7px] rounded-btn border border-btn-border bg-base px-4 text-sm text-ink-2 disabled:opacity-50";
const EYEBROW = "font-mono text-[11px] font-semibold tracking-[0.14em] text-brand";
type TextField = "q1" | "q2" | "q3" | "q3_1" | "q3_2" | "q4_1" | "founder_strength";

export function IdeaFormClient() {
  const router = useRouter();
  const [draft, setDraft] = useState<IdeaInput>(EMPTY);
  const [limits, setLimits] = useState(DEFAULT_LIMITS);
  const [categories, setCategories] = useState(FIELDS);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showIdeaExtra, setShowIdeaExtra] = useState(false);
  const [showPlanExtra, setShowPlanExtra] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const loaded = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      const current = localStorage.getItem(DRAFT_KEY);
      const old = localStorage.getItem("soul.idea.draft");
      if (current) {
        const saved = JSON.parse(current) as Partial<IdeaInput>;
        // The old form had one combined idea field. Keep the user's wording visible in both new fields.
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Restore one external browser draft.
        setDraft({ ...EMPTY, ...saved, q3: saved.q3 || saved.q3_1 || "", evidence: Array.isArray(saved.evidence) ? saved.evidence : [] });
        setShowIdeaExtra(!!(saved.q2 || saved.q3_2));
        setShowPlanExtra(!!(saved.q4_1 || saved.founder_strength));
        setShowEvidence(!!saved.evidence?.length);
      } else if (old) {
        const saved = JSON.parse(old);
        setDraft({ ...EMPTY, q1: saved.oneLiner ?? "", q2: saved.background ?? "", q3: saved.description ?? saved.problemAndDiff ?? "", q3_1: saved.problemAndDiff ?? saved.description ?? "", q3_2: saved.revenueModel ?? "", q4_1: saved.executionPlan ?? "", founder_strength: saved.founderStrength ?? "", q5: saved.field ?? "IT", customer_type: CUSTOMERS.includes(saved.customerType) ? saved.customerType : EMPTY.customer_type });
        setShowIdeaExtra(!!(saved.background || saved.revenueModel));
        setShowPlanExtra(!!(saved.executionPlan || saved.founderStrength));
      }
    } catch { /* Browser storage may be unavailable. */ }
    loaded.current = true;
    void api<InputLimits>("/limits").then(setLimits).catch(() => {});
    void api<string[]>("/categories").then(setCategories).catch(() => {});
  }, []);
  useEffect(() => {
    if (!loaded.current) return;
    const timer = setTimeout(() => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); setSavedAt(Date.now()); } catch {} }, 500);
    return () => clearTimeout(timer);
  }, [draft]);

  const set = (key: TextField) => (value: string) => setDraft(previous => ({ ...previous, [key]: value }));
  const evidenceTotal = draft.evidence.reduce((sum, item) => sum + item.text.length, 0);
  const activeEvidence = draft.evidence.filter(item => item.text.trim());
  const withinLimits = (["q1", "q2", "q3", "q3_1", "q3_2", "q4_1", "founder_strength"] as TextField[]).every(key => draft[key].length <= limits[key]);
  const ready = !!draft.q1.trim() && !!draft.q3.trim() && !!draft.q3_1.trim() && categories.includes(draft.q5) && CUSTOMERS.includes(draft.customer_type) && withinLimits && evidenceTotal <= limits.evidence_total && activeEvidence.every(e => !!e.source_id.trim() && e.text.length <= limits.evidence_text);
  async function submit() {
    if (!ready || busy) return;
    setBusy(true); setError(null);
    try { await createSession({ ...draft, evidence: activeEvidence }); router.push("/targets"); }
    catch (err) { setError(err instanceof Error ? err.message : "타깃을 추천받지 못했습니다."); }
    finally { setBusy(false); }
  }
  function updateEvidence(index: number, update: Partial<Evidence>) { setDraft(previous => ({ ...previous, evidence: previous.evidence.map((e, i) => i === index ? { ...e, ...update } : e) })); }
  function addEvidence() {
    if (draft.evidence.length >= limits.evidence_count) return;
    setShowEvidence(true);
    setDraft(previous => ({ ...previous, evidence: [...previous.evidence, { source_id: `자료-${Date.now()}`, text: "", level: 0, consent_note: "UNKNOWN" }] }));
  }
  async function uploadFile(file?: File) {
    if (!file) return;
    if (!/\.(txt|md|csv)$/i.test(file.name)) { setError("TXT, MD, CSV 파일을 선택해 주세요. PDF는 필요한 부분을 복사해 원문 발췌에 붙여 넣을 수 있어요."); return; }
    if (file.size > 1024 * 1024) { setError("파일은 1MB 이하로 올려주세요. 필요한 부분만 남기면 분석도 빨라집니다."); return; }
    if (draft.evidence.length >= limits.evidence_count) { setError(`자료는 최대 ${limits.evidence_count}개입니다.`); return; }
    try {
      const contents = await file.text();
      if (!contents.trim() || contents.length > limits.evidence_text || evidenceTotal + contents.length > limits.evidence_total) { setError(`자료 원문은 건당 ${limits.evidence_text}자, 전체 ${limits.evidence_total}자까지입니다. 관련 부분만 발췌해 주세요.`); return; }
      setDraft(previous => ({ ...previous, evidence: [...previous.evidence, { source_id: `${file.name.slice(0, 60)}-${Date.now()}`, text: contents, level: 0, consent_note: "UNKNOWN" }] }));
      setShowEvidence(true); setError(null);
    } catch { setError("파일을 읽지 못했습니다. 관련 문장을 원문 발췌 칸에 직접 붙여 넣어 주세요."); }
    finally { if (fileInput.current) fileInput.current.value = ""; }
  }
  function field(key: TextField, label: string, options: { required?: boolean; rows?: number; placeholder?: string } = {}) {
    const limit = limits[key];
    return <div className="flex min-w-0 grow basis-0 flex-col gap-[7px]"><label htmlFor={key} className="text-sm font-medium text-ink-2">{label}{options.required && <span className="ml-1 text-conflict-fg">*</span>}</label>{key === "q1" ? <input id={key} type="text" value={draft[key]} onChange={event => set(key)(event.target.value)} maxLength={limit} className={INPUT} /> : <textarea id={key} rows={options.rows ?? 3} value={draft[key]} onChange={event => set(key)(event.target.value)} placeholder={options.placeholder} maxLength={limit} className={AREA} />}<span className="self-end text-xs text-muted">{draft[key].length} / {limit}자</span></div>;
  }
  return <>
    <AppHeader current="01" right={savedAt ? <p className="text-[13px] text-muted">방금 저장됨</p> : undefined} />
    <main className="flex grow flex-col gap-5 px-[26px] py-[34px] lg:px-[120px]">
      <div className="flex flex-col gap-2"><p className="font-mono text-xs tracking-[0.14em] text-muted">STEP 01</p><h1 className="text-[30px] font-bold leading-[1.36] tracking-[-0.022em]">아이디어를 문장으로 적습니다</h1><p className="text-[15px] leading-[1.7] text-ink-3">여기 적은 내용을 바탕으로 만나볼 사람을 찾아드려요. 별표 표시된 네 칸만 채우면 시작할 수 있어요.</p></div>
      <section className={CARD}><div className="flex items-center gap-2.5"><h2 className={EYEBROW}>기본</h2><p className="text-[13px] text-muted">필수 2개</p></div>
        {field("q1", "아이디어를 한 줄로 소개해주세요", { required: true })}
        <div className="flex flex-col gap-4 sm:flex-row"><div className="flex min-w-0 grow basis-0 flex-col gap-[7px]"><label htmlFor="q5" className="text-sm font-medium text-ink-2">사업 분야 <span className="text-conflict-fg">*</span></label><select id="q5" value={draft.q5} onChange={event => setDraft(previous => ({ ...previous, q5: event.target.value }))} className={INPUT}>{categories.map(category => <option key={category}>{category}</option>)}</select></div><div className="flex min-w-0 grow basis-0 flex-col gap-[7px]"><label htmlFor="customer_type" className="text-sm font-medium text-ink-2">고객 유형</label><select id="customer_type" value={draft.customer_type} onChange={event => setDraft(previous => ({ ...previous, customer_type: event.target.value as IdeaInput["customer_type"] }))} className={INPUT}>{CUSTOMERS.map(customer => <option key={customer}>{customer}</option>)}</select></div></div>
      </section>
      <section className={CARD}><div className="flex items-center gap-2.5"><h2 className={EYEBROW}>아이디어</h2><p className="text-[13px] text-muted">필수 2개 · 선택 2개</p></div>
        <div className="flex flex-col gap-4 md:flex-row">{field("q3", "어떤 아이디어인가요", { required: true, rows: 4 })}{field("q3_1", "어떤 문제를 풀고, 기존 방식과 뭐가 다른가요", { required: true, rows: 4, placeholder: "예) 지금은 주변 사람이나 AI에게 혼자 물어보는데, 한 명씩만 답해서 의견이 갈리는 지점을 볼 수 없습니다." })}</div>
        {showIdeaExtra ? <div className="flex flex-col gap-4 md:flex-row">{field("q2", "어떻게 떠올리셨나요")}{field("q3_2", "어떻게 돈을 버나요")}</div> : <button type="button" onClick={() => setShowIdeaExtra(true)} className={`${SECONDARY} self-start text-brand`}>＋ 선택 문항 더 쓰기 — 떠올린 배경, 수익 모델</button>}
      </section>
      <section className={CARD}><div className="flex flex-wrap items-center gap-3"><div className="min-w-[220px] grow"><h2 className="text-[16px] font-semibold">실현 계획 · 자료</h2><p className="mt-1 text-sm leading-relaxed text-ink-3">사업화 계획과 본인 역량은 선택이에요. 기획서나 설문 결과 중 관련 부분도 추가할 수 있어요.</p></div><input ref={fileInput} type="file" accept=".txt,.md,.csv,text/plain,text/markdown,text/csv" className="sr-only" aria-label="텍스트 자료 파일 선택" aria-hidden="true" tabIndex={-1} onChange={event => void uploadFile(event.target.files?.[0])} /><button type="button" onClick={() => fileInput.current?.click()} className={`${SECONDARY} border-dashed bg-input`}>↑ 파일 올리기</button><button type="button" onClick={() => setShowPlanExtra(value => !value)} aria-expanded={showPlanExtra} className={SECONDARY}>{showPlanExtra ? "선택 문항 접기" : "선택 문항 열기"}</button></div><p className="text-xs text-muted">파일: TXT · MD · CSV, 1MB 이하 · 개인정보를 지우고 올려주세요. PDF는 관련 문장을 아래에 붙여 넣어주세요.</p>
        {showPlanExtra && <div className="flex flex-col gap-4 md:flex-row">{field("q4_1", "앞으로 어떻게 만들 계획인가요")}{field("founder_strength", "본인이 잘하는 것")}</div>}
        <div className="flex flex-wrap items-center gap-3"><button type="button" onClick={() => setShowEvidence(value => !value)} aria-expanded={showEvidence} className={SECONDARY}>{showEvidence ? "원문 발췌 접기" : "원문 발췌 보기"}</button><button type="button" onClick={addEvidence} disabled={draft.evidence.length >= limits.evidence_count} className={SECONDARY}>＋ 원문 발췌 추가</button><span className="text-xs text-muted">{draft.evidence.length} / {limits.evidence_count}개 · 전체 {evidenceTotal} / {limits.evidence_total}자</span></div>
        {showEvidence && <div className="flex flex-col gap-4">{draft.evidence.map((e, index) => <div key={`${e.source_id}-${index}`} className="flex flex-col gap-2 rounded-[12px] border border-divider p-4"><div className="flex flex-wrap items-center gap-3"><label className="flex min-w-[180px] grow items-center gap-2 text-sm">자료 이름<input value={e.source_id} maxLength={80} onChange={event => updateEvidence(index, { source_id: event.target.value })} className={INPUT} /></label><select aria-label={`자료 ${index + 1} 유형`} value={e.level} onChange={event => updateEvidence(index, { level: Number(event.target.value) as Evidence["level"] })} className={`${INPUT} max-w-64`}>{[0, 1, 2, 3, 4].map(level => <option key={level} value={level}>{evidenceInputLabel(level)}</option>)}</select><button type="button" className={SECONDARY} onClick={() => setDraft(previous => ({ ...previous, evidence: previous.evidence.filter((_, i) => i !== index) }))}>삭제</button></div><textarea aria-label={`자료 ${index + 1} 원문 발췌`} rows={4} value={e.text} maxLength={limits.evidence_text} onChange={event => updateEvidence(index, { text: event.target.value })} className={AREA} /><p className="self-end text-xs text-muted">{e.text.length} / {limits.evidence_text}자</p><label className="text-sm text-ink-3">사용 허가·수집 맥락<input value={e.consent_note === "UNKNOWN" ? "" : e.consent_note} onChange={event => updateEvidence(index, { consent_note: event.target.value || "UNKNOWN" })} maxLength={500} className={`${INPUT} mt-1`} /></label></div>)}</div>}
      </section>
      {error && <div role="alert" className="rounded-card bg-conflict-bg p-4 text-sm leading-relaxed text-conflict-fg">진행하지 못했습니다: {error}</div>}
      <div className="mt-auto flex flex-wrap items-center gap-4 pt-2"><p role="status" className="grow text-sm text-muted">{busy ? "아이디어에 맞는 타깃을 찾고 있어요." : "작성한 내용은 이 브라우저에 자동으로 저장돼요. 별표 칸을 채우면 시작할 수 있어요."}</p><button type="button" onClick={() => void submit()} disabled={!ready || busy} className="h-12 shrink-0 rounded-btn bg-brand px-[26px] text-[15px] font-semibold text-white disabled:bg-bubble disabled:text-muted">{busy ? "타깃 추천 중…" : "타깃 찾아보기"}</button></div>
    </main>
  </>;
}
