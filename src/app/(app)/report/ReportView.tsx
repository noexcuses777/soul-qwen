"use client";

import { useMemo, useState } from "react";
import { PersonaAvatar } from "@/components/PersonaAvatar";
import { normalize } from "@/lib/korean-text";
import { evidenceDescription, evidenceLabel } from "@/lib/evidence-presentation";
import type { PersonaColor } from "@/lib/types";
import type { ReportInsight, ReportSource, ReportStance, ReportTopic, SoulReportView } from "./report-types";
import styles from "./report.module.css";

const STANCE: Record<ReportStance, { label: string; className: string }> = {
  positive: { label: "긍정", className: "bg-agree-bg text-agree-fg" },
  conditional: { label: "조건부", className: "bg-conflict-bg text-conflict-fg" },
  negative: { label: "부정", className: "bg-ink-2 text-white" },
  unknown: { label: "미확인", className: "bg-bubble text-ink-3" },
};

const SECTION_LABELS: Record<string, string> = {
  "Target Snapshot": "타깃 요약", "Problem Signal": "문제 반응", "Solution Reaction": "서비스 반응",
  "Target Differences": "타깃 간 차이", Agreement: "공통 반응", Disagreement: "의견 차이",
  "Unknown/Unsupported": "미확인·근거 부족", "Real Interview Next Steps": "실제 인터뷰 계획",
};

type DisplaySource = ReportSource & { referenceLabel: string };
function phaseLabel(phase: string) {
  return phase === "pre" ? "비공개 사전" : phase === "post" ? "비공개 사후" : phase === "group" ? "공개 대화" : "대화 기록";
}

function sourceIndex(sources: ReportSource[]): Map<string, DisplaySource> {
  const counts = new Map<string, number>();
  return new Map(sources.map(source => {
    const count = (counts.get(source.phase) ?? 0) + 1;
    counts.set(source.phase, count);
    return [source.id, { ...source, referenceLabel: `${source.name} · ${phaseLabel(source.phase)} ${count}번 발언` }];
  }));
}

function referenceText(ids: string[], sources: Map<string, DisplaySource>) {
  return [...new Set(ids)].map(id => sources.get(id)?.referenceLabel ?? "발언 원문 미확인").join(", ") || "연결된 발언 없음";
}

const PROTECTED_PROSE = /(```[\s\S]*?(?:```|$)|`[^`\r\n]*`|https?:\/\/[^\s<>]+|"[^"\r\n]*"|'[^'\r\n]*'|“[^”\r\n]*”|‘[^’\r\n]*’)/g;
const INTERNAL_REFERENCE = /(?<![\p{L}\p{N}_])(?:L[0-4]|u\d+)(?![\p{L}\p{N}_])/gu;
/** Format generated interpretation only; never run on verbatim source/user text. */
function insightText(insight: Pick<ReportInsight, "text" | "utterance_ids">, sources: Map<string, DisplaySource>) {
  const cited = new Set(insight.utterance_ids);
  return normalize(insight.text.split(PROTECTED_PROSE).map((part, index) => index % 2 ? part : part.replace(INTERNAL_REFERENCE, token =>
    token.startsWith("L") ? evidenceLabel(Number(token.slice(1))) :
      cited.has(token) ? sources.get(token)?.referenceLabel ?? "발언 원문 미확인" : "연결되지 않은 발언 참조"
  )).join(""));
}

const QUALITY_LABELS: Record<string, string> = {
  unsupported_quantity: "근거 없는 수치 표현",
  unsupported_experience: "확인되지 않은 경험 표현",
  purchase_overclaim: "구매 의사 확정 표현",
  persona_identity_mismatch: "인물 역할 혼동",
  persona_self_address: "응답 대상 혼동",
  response_repeat: "이전 답변 반복",
  response_repetition: "이전 답변 반복",
};
function qualityNote(flags: string[]) {
  return [...new Set(flags.map(flag => {
    const base = flag.replace(/_(repaired|unresolved|withheld)$/, "");
    const label = QUALITY_LABELS[base];
    if (!label) return "생성 검사 표시 · 추가 확인 필요";
    const action = flag.endsWith("_repaired") ? "다시 생성해 보완" : flag.endsWith("_unresolved") ? "추가 검토 필요" : flag.endsWith("_withheld") ? "판단 보류" : "표현 교정 또는 판단 보류";
    return `${label} · ${action}`;
  }))].join(" / ");
}

function verdict(topic: ReportTopic, people: SoulReportView["meta"]["participants"]) {
  const known = topic.positions.filter((p) => p.utterance_id);
  const positive = known.filter((p) => p.stance === "positive").length;
  const negative = known.filter((p) => p.stance === "negative").length;
  const covered = people.length > 0 && people.every((person) => known.some((p) => p.persona_id === person.id));
  if (covered && positive === people.length) return { label: "참여자 모두 긍정 반응", className: "bg-agree-bg text-agree-fg" };
  if (positive > 0 && negative > 0) return { label: `긍정 ${positive} · 부정 ${negative}`, className: "bg-conflict-bg text-conflict-fg" };
  if (known.some((p) => p.stance === "conditional")) return { label: "조건 확인 필요", className: "bg-conflict-bg text-conflict-fg" };
  return { label: "확정 결론 없음", className: "bg-bubble text-ink-3" };
}

function Evidence({ ids, evidenceIds = [], sources, level }: {
  ids: string[]; evidenceIds?: string[]; sources: Map<string, DisplaySource>; level?: number;
}) {
  const unique = [...new Set(ids)];
  return (
    <div className="mt-2 text-[11px] leading-relaxed text-muted">
      {level !== undefined ? <p title={evidenceDescription(level)}>{evidenceLabel(level)}</p> : null}
      {evidenceIds.length ? <p className="break-all">참고 자료: {evidenceIds.join(", ")}</p> : null}
      {unique.length ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-brand">근거 발언 {unique.length}개 보기</summary>
          <ul className="mt-2 flex flex-col gap-2">
            {unique.map((id) => {
              const source = sources.get(id);
              return (
                <li key={id} data-source-id={id} className="rounded-[9px] border border-line bg-panel p-3">
                  <p className="font-medium">{source?.referenceLabel ?? "발언 원문을 찾을 수 없음"}</p>
                  {source ? <blockquote className={`mt-1 text-xs text-ink-2 ${styles.copy}`}>{source.content}</blockquote> : null}
                  {source?.quality_flags.length ? <p className="mt-1 text-conflict-fg">생성 검사: {qualityNote(source.quality_flags)}</p> : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : <p>발화 근거 없음 · 확인할 질문 또는 미확인 항목</p>}
    </div>
  );
}

function InsightContent({ insight, sources }: { insight: ReportInsight; sources: Map<string, DisplaySource> }) {
  return <><p className={`text-sm leading-[1.8] text-ink-2 ${styles.copy}`}>{insightText(insight, sources)}</p><Evidence ids={insight.utterance_ids} evidenceIds={insight.evidence_ids} sources={sources} level={insight.evidence_level} /></>;
}

function reportMetrics(report: SoulReportView) {
  return [
    { label: "다룬 질문", value: report.meta.question_count, className: "text-ink" },
    { label: "긍정·부정이 갈린 질문", value: report.topics.filter((topic) => topic.positions.some((p) => p.stance === "positive" && p.utterance_id) && topic.positions.some((p) => p.stance === "negative" && p.utterance_id)).length, className: "text-conflict-fg" },
    { label: "입장 표현 변화", value: report.changes.length, className: "text-agree-fg" },
    { label: "추출한 인사이트", value: report.new_insights.length, className: "text-ink" },
  ];
}

export function reportText(report: SoulReportView) {
  const people = report.meta.participants;
  const sources = sourceIndex(report.sources);
  const refs = (ids: string[]) => referenceText(ids, sources);
  return [
    "Soul 분석 리포트", report.notice,
    `세션: ${report.meta.session_id} · 리포트 시점: 공개 발화 ${report.meta.revision}`,
    `참여자: ${people.map((p) => `${p.name} (${p.segment})`).join(" · ")}`,
    `생성일: ${report.meta.generated_at ? new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short" }).format(new Date(report.meta.generated_at)) : "미기록"} · 공개 발언 ${report.meta.public_turn_count}개`,
    report.meta.stale ? "이 리포트 이후 대화가 추가되었습니다. 현재 저장된 시점의 내용입니다." : "",
    "", "결론", ...report.conclusion.map((x) => `${insightText(x, sources)}\n  근거: ${refs(x.utterance_ids)} · ${evidenceLabel(x.evidence_level)}`),
    "", ...reportMetrics(report).map((metric) => `${metric.label}: ${metric.value}`),
    "", "쟁점", ...report.topics.flatMap((topic, i) => [
      `${i + 1}. ${topic.question} — ${verdict(topic, people).label}`,
      ...topic.positions.map((p) => `${p.name} (${STANCE[p.stance].label}): ${p.content}\n  이유: ${p.reason}\n  근거: ${p.utterance_id ? refs([p.utterance_id]) : "해당 질문의 발언 없음"}`),
      ...topic.insights.map((x) => `해석: ${insightText(x, sources)}\n  근거: ${refs(x.utterance_ids)}`),
    ]),
    "", "대화에서 얻은 인사이트", ...report.new_insights.map((x) => `${insightText(x, sources)}\n  근거: ${refs(x.utterance_ids)} · ${evidenceLabel(x.evidence_level)}`),
    "", "입장 표현 변화", ...report.changes.map((x) => `${x.name} · ${x.question}: ${STANCE[x.before.stance].label} → ${STANCE[x.after.stance].label}\n  이유: ${x.after.reason}\n  근거: ${refs(x.utterance_ids)}`),
    "", "이어서 물어볼 질문", ...report.followups.map((x) => x.question),
    "", "확인하지 못한 것", ...report.unknowns.map((x) => insightText(x, sources)),
    "", "실제로 만나서 물어볼 것", "누구를", ...people.map((p) => p.segment),
    "무엇을", ...report.real_interview.map((x, i) => `${i + 1}. ${insightText(x, sources)}`),
    "", "8개 분석 항목", ...Object.entries(report.sections).flatMap(([section, rows]) => [SECTION_LABELS[section] || section, ...rows.map((x) => `${insightText(x, sources)}\n  근거: ${refs(x.utterance_ids)} · 자료: ${x.evidence_ids.join(", ") || "없음"} · ${evidenceLabel(x.evidence_level)}`)]),
    "", "근거 발언 원문", ...report.sources.map((source) => `${sources.get(source.id)!.referenceLabel}\n${source.content}\n이유: ${source.reason}`),
    "", report.meta.metrics_notice,
  ].join("\n");
}

function saveFile(content: string, type: string, name: string) {
    const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ReportDownloadButton({ report }: { report: SoulReportView }) {
  const [open, setOpen] = useState(false);
  return <div className="relative" data-report-controls>
    <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="h-11 rounded-btn border border-btn-border bg-base px-4 text-sm text-ink-2">내려받기</button>
    {open ? <div className="absolute right-0 z-20 mt-2 flex min-w-44 flex-col gap-1 rounded-card border border-card bg-base p-2">
      <button type="button" className="rounded-btn px-3 py-2 text-left text-sm hover:bg-panel" onClick={() => { saveFile(reportText(report), "text/plain;charset=utf-8", `soul-report-${report.meta.session_id}.txt`); setOpen(false); }}>텍스트 내려받기</button>
      <button type="button" className="rounded-btn px-3 py-2 text-left text-sm hover:bg-panel" onClick={() => { saveFile(JSON.stringify(report, null, 2), "application/json;charset=utf-8", `soul-report-${report.meta.session_id}.json`); setOpen(false); }}>JSON 내려받기</button>
      <button type="button" className="rounded-btn px-3 py-2 text-left text-sm hover:bg-panel" onClick={() => { setOpen(false); window.print(); }}>인쇄 / PDF 저장</button>
    </div> : null}
  </div>;
}

export function ReportClient({ report, regenerating, onRegenerate, onContinue, onAsk, onNewTargets, mode, colors }: {
  report: SoulReportView; regenerating: boolean; onRegenerate: () => void; onContinue: () => void;
  onAsk: (question: string, personaId: string | null) => void; onNewTargets: () => void; mode: "mock" | "qwen"; colors?: Record<string, PersonaColor>;
}) {
  const [copied, setCopied] = useState<"idle" | "done" | "fail">("idle");
  const sources = useMemo(() => sourceIndex(report.sources), [report.sources]);
  const people = report.meta.participants;
  const colorOf = (id: string) => colors?.[id] ?? ((Math.max(0, people.findIndex((person) => person.id === id)) % 5) + 1) as PersonaColor;
  const stats = reportMetrics(report);
  const copyQuestions = async () => {
    try { await navigator.clipboard.writeText(report.real_interview.map((x, i) => `${i + 1}. ${insightText(x, sources)}`).join("\n")); setCopied("done"); }
    catch { setCopied("fail"); }
  };
  return <main className={`${styles.body} flex grow flex-col gap-[26px]`}>
    <section className="flex flex-col gap-3.5" aria-labelledby="report-title">
      <p className="flex flex-wrap items-center gap-x-3.5 gap-y-1 font-mono text-[11px] tracking-[0.07em] text-muted">
        <span>{report.meta.generated_at ? new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "medium" }).format(new Date(report.meta.generated_at)) : "생성 날짜 미기록"}</span>
        <span aria-hidden="true">·</span><span>{people.map((person) => person.name).join(" · ")}</span>
        <span aria-hidden="true">·</span><span>질문 {report.meta.question_count}개 · 공개 발언 {report.meta.public_turn_count}개</span>
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 id="report-title" className="text-[30px] font-bold tracking-[-0.024em]">분석 리포트</h1><button type="button" onClick={onRegenerate} disabled={regenerating} data-report-controls className="rounded-btn border border-btn-border bg-base px-4 py-2 text-sm text-ink-2 disabled:opacity-50">{regenerating ? "현재 대화로 갱신 중…" : "현재 대화로 리포트 갱신"}</button></div>
      <p className="rounded-[11px] border border-action-border bg-action-bg p-3 text-sm leading-relaxed text-brand">{mode === "mock" ? "데모 모드 · 합성 응답이며 실제 Qwen 출력이나 성능 검증 결과가 아닙니다. " : ""}{report.notice}</p>
      <details className="rounded-[11px] border border-line bg-base p-3 text-xs leading-relaxed text-muted"><summary className="cursor-pointer font-medium text-ink-2">근거 표시 안내</summary><p className="mt-2">근거 표시는 참고한 자료의 종류입니다. 정확도 점수나 시장 검증 결과가 아닙니다.</p><ul className="mt-2 flex flex-col gap-1">{[0, 1, 2, 3, 4].map(level => <li key={level}>{evidenceLabel(level)}</li>)}</ul><p className="mt-2">‘근거 발언 보기’를 펼치면 이름과 대화 단계, 발언 순서로 연결된 원문을 확인할 수 있습니다.</p></details>
      {report.meta.excluded_insight_count > 0 ? <p className="text-xs leading-relaxed text-conflict-fg">근거 발화를 연결할 수 없는 분석 {report.meta.excluded_insight_count}건은 본문에서 제외했습니다. 연결된 원문과 미확인 항목을 함께 확인하세요.</p> : null}
      {report.meta.stale ? <p role="status" className="rounded-[11px] border border-card bg-conflict-bg p-3 text-sm leading-relaxed text-conflict-fg">이 리포트 이후 대화가 추가되었습니다. 공개 발언 {report.meta.revision}개까지의 저장된 내용입니다. 최신 대화를 포함하려면 리포트를 갱신하세요.</p> : null}
      <div className="flex flex-col gap-3.5 rounded-card border border-card bg-base px-5 py-6 sm:px-7">
        <p className="font-mono text-[11px] font-semibold tracking-[0.14em] text-brand">결론 · 이 세션에서 관찰한 반응</p>
        {report.conclusion.length ? report.conclusion.map((insight, index) => <div key={`${insight.section}-${index}`}><p className={`${index === 0 ? "text-xl font-semibold leading-[1.6]" : "text-[16px] leading-[1.8] text-ink-2"} ${styles.copy}`}>{insightText(insight, sources)}</p><Evidence ids={insight.utterance_ids} evidenceIds={insight.evidence_ids} sources={sources} level={insight.evidence_level} /></div>) : <p className="text-sm text-muted">근거를 연결할 수 있는 결론이 아직 없습니다.</p>}
      </div>
    </section>

    <div><dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">{stats.map((stat) => <div key={stat.label} className="flex flex-col gap-1.5 rounded-card border border-card bg-base px-[18px] py-4"><dt className="text-xs text-muted">{stat.label}</dt><dd className={`font-mono text-2xl font-semibold ${stat.className}`}>{stat.value}</dd></div>)}</dl><p className="mt-2 text-xs leading-relaxed text-muted">수치는 이 대화의 기록이며 시장 통계나 구매 확률이 아닙니다.</p></div>

    <section className="flex flex-col gap-3.5" aria-labelledby="topics-title">
      <div className="flex flex-wrap items-baseline gap-3"><h2 id="topics-title" className="text-xl font-semibold">쟁점</h2><p className="text-sm text-muted">질문 순서에 따라 참여자 반응을 비교합니다.</p></div>
      {report.topics.length ? report.topics.map((topic, index) => {
        const badge = verdict(topic, people);
        return <article key={topic.id} className="flex flex-col gap-3.5 rounded-card border border-card bg-base px-5 py-5 sm:px-6">
          <div className="flex flex-wrap items-start gap-3"><span className="pt-1 font-mono text-xs font-semibold text-muted">{String(index + 1).padStart(2, "0")}</span><h3 className={`min-w-0 flex-1 text-[17px] font-semibold ${styles.copy}`}>{topic.question}</h3><span className={`rounded-[9px] px-3 py-1.5 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span></div>
          <ul className="flex flex-col gap-4">{topic.positions.map((position) => <li key={position.persona_id} className="flex min-w-0 items-start gap-3">
            <PersonaAvatar name={position.name} color={colorOf(position.persona_id)} size="sm" />
            <div className="min-w-0 grow"><div className="mb-1 flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{position.name}</span><span className={`rounded-[9px] px-2.5 py-1 text-xs font-semibold ${STANCE[position.stance].className}`}>{STANCE[position.stance].label}</span><span className="text-xs text-muted">{position.segment}</span></div>
              <p className={`text-sm leading-[1.75] text-ink-2 ${styles.copy}`}>{position.utterance_id ? normalize(position.content) : "해당 질문에 연결된 공개 발언이 없습니다."}</p>
              {position.reason && position.reason !== "UNKNOWN" ? <p className={`mt-1 text-xs leading-relaxed text-muted ${styles.copy}`}>판단 이유: {normalize(position.reason)}</p> : null}
              <Evidence ids={position.utterance_id ? [position.utterance_id] : []} evidenceIds={position.evidence_ids} sources={sources} />
            </div>
          </li>)}</ul>
          {topic.insights.length ? <div className="rounded-[11px] bg-panel px-4 py-3"><p className="mb-2 font-mono text-[11px] font-semibold text-muted">해석 · 확인할 가설</p>{topic.insights.map((insight, i) => <div key={i} className={i ? "mt-3" : ""}><InsightContent insight={insight} sources={sources} /></div>)}</div> : <p className="rounded-[11px] bg-panel p-3 text-xs leading-relaxed text-muted">이 질문만으로 원인을 확정할 수 없습니다. 위 발언의 조건과 근거를 실제 인터뷰에서 확인하세요.</p>}
        </article>;
      }) : <p className="rounded-card border border-card bg-base p-5 text-sm text-muted">쟁점별로 연결할 공개 대화가 없습니다. 대화창에서 질문한 뒤 리포트를 갱신하세요.</p>}
    </section>

    <section className="flex flex-col gap-3.5" aria-labelledby="insights-title"><div className="flex flex-wrap items-baseline gap-3"><h2 id="insights-title" className="text-xl font-semibold">대화에서 얻은 인사이트</h2><p className="text-sm text-muted">이 세션에서 나온 가설 · 실제 고객에게 확인할 내용</p></div><ol className="flex flex-col gap-5 rounded-card border border-card bg-base px-5 py-[22px] sm:px-[26px]">{report.new_insights.length ? report.new_insights.map((insight, index) => <li key={index} className="flex items-start gap-4"><span className="pt-1 font-mono text-xs font-semibold text-brand">{String(index + 1).padStart(2, "0")}</span><div className="min-w-0 grow"><InsightContent insight={insight} sources={sources} /></div></li>) : <li className="text-sm text-muted">근거를 연결할 수 있는 인사이트가 아직 없습니다.</li>}</ol></section>

    <div className="grid gap-[18px] xl:grid-cols-3">
      <section className="flex flex-col gap-3 rounded-card border border-card bg-base px-[22px] py-5"><h2 className="text-[16px] font-semibold">입장이 바뀐 지점</h2>{report.changes.length ? report.changes.map((change, index) => <div key={`${change.topic_id}-${change.persona_id}-${index}`} className="border-b border-line pb-3 last:border-0"><p className="text-sm font-medium">{change.name}</p><p className="mt-1 text-xs leading-relaxed text-muted">{change.question}</p><p className="my-2 text-sm"><span className="rounded-[9px] bg-bubble px-2 py-1">{STANCE[change.before.stance].label}</span><span className="px-2" aria-label="에서">→</span><span className="rounded-[9px] bg-action-bg px-2 py-1 text-brand">{STANCE[change.after.stance].label}</span></p><p className="text-xs leading-relaxed text-muted">{change.basis}</p><p className={`mt-2 text-sm leading-relaxed text-ink-2 ${styles.copy}`}>이후 판단 이유: {change.after.reason === "UNKNOWN" ? "미확인" : normalize(change.after.reason)}</p><Evidence ids={change.utterance_ids} sources={sources} /></div>) : <p className="text-sm leading-[1.75] text-ink-2">근거로 확인할 수 있는 입장 변화가 없습니다.</p>}</section>
      <section className="flex flex-col gap-3 rounded-card border border-card bg-base px-[22px] py-5"><h2 className="text-[16px] font-semibold">이어서 물어볼 지점</h2><p className="text-sm leading-[1.75] text-ink-2">질문을 누르면 대화창에 초안이 채워집니다. 내용을 확인한 뒤 직접 보내세요.</p><div className="flex flex-col gap-2">{report.followups.length ? report.followups.map((followup, index) => { const person = people.find((p) => p.id === followup.persona_id); return <div key={index}><button type="button" onClick={() => onAsk(followup.question, followup.persona_id)} className="flex w-full items-start gap-2 rounded-[11px] border border-action-border bg-action-bg px-3 py-3 text-left text-[13px] leading-[1.6] text-brand" data-report-action>{person ? <PersonaAvatar name={person.name} color={colorOf(person.id)} size="sm" /> : <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand text-[10px] font-semibold text-white" aria-hidden="true">모두</span>}<span className="min-w-0 grow"><span className="sr-only">{person ? `${person.name}에게: ` : "참여자 모두에게: "}</span>{normalize(followup.question)}</span></button>{followup.why && followup.why !== "UNKNOWN" ? <p className="mt-1 px-1 text-xs leading-relaxed text-muted">{normalize(followup.why)}</p> : null}</div>; }) : <p className="text-sm text-muted">저장된 후속 질문이 없습니다. 대화창에서 자유롭게 물어볼 수 있습니다.</p>}</div></section>
      <section className="flex flex-col gap-3 rounded-card border border-card bg-base px-[22px] py-5"><h2 className="text-[16px] font-semibold">확인하지 못한 것</h2><ul className="flex flex-col gap-3">{report.unknowns.length ? report.unknowns.map((unknown, index) => <li key={index}><p className={`text-sm leading-[1.75] text-ink-2 ${styles.copy}`}>{insightText(unknown, sources)}</p><Evidence ids={unknown.utterance_ids} evidenceIds={unknown.evidence_ids} sources={sources} /></li>) : <li className="text-sm leading-relaxed text-muted">기록된 미확인 항목이 없습니다. 실제 지불·재방문·구매 결정은 AI 대화만으로 확인할 수 없습니다.</li>}</ul></section>
    </div>

    <section className="report-real-interview flex flex-col gap-8 rounded-card bg-dark-bg px-5 py-[26px] lg:flex-row lg:gap-11 lg:px-[30px]">
      <div className="flex flex-col gap-3 lg:w-[300px] lg:shrink-0"><h2 className="text-[19px] font-semibold text-dark-ink">실제로 만나서 물어볼 것</h2><p className="text-sm leading-[1.75] text-dark-ink-2">위 대화는 실제 고객의 답이 아닙니다. 아래 질문으로 실제 경험과 행동을 확인하세요.</p><h3 className="mt-1 font-mono text-[10px] font-semibold tracking-[0.12em] text-brand-on-dark">누구를</h3><ul className="flex flex-col gap-2">{[...new Set(people.map((person) => person.segment))].map((segment) => <li key={segment} className={`text-sm leading-[1.9] text-dark-ink-2 ${styles.copy}`}>· {segment}에 해당하는 실제 이용자</li>)}</ul><p className="text-xs leading-relaxed text-dark-ink-2">모집 인원·조건은 검증하려는 가설과 현장 상황에 맞춰 정하세요.</p></div>
      <div className="min-w-0 grow"><h3 className="mb-3 font-mono text-[10px] font-semibold tracking-[0.12em] text-brand-on-dark">무엇을</h3><ol className="flex flex-col gap-3">{report.real_interview.length ? report.real_interview.map((insight, index) => <li key={index} className="flex items-start gap-3"><span className="pt-1 font-mono text-[11px] font-semibold text-brand-on-dark">{String(index + 1).padStart(2, "0")}</span><span className={`min-w-0 grow text-sm leading-[1.7] text-dark-ink ${styles.copy}`}>{insightText(insight, sources)}</span></li>) : <li className="text-sm text-dark-ink-2">근거가 충분한 인터뷰 질문이 아직 없습니다. 미확인 항목을 보완한 뒤 다시 정리해 주세요.</li>}</ol><button type="button" onClick={copyQuestions} disabled={!report.real_interview.length} data-report-controls className="mt-4 h-11 rounded-btn bg-green-pure px-[18px] text-sm font-semibold text-ink disabled:opacity-50">{copied === "done" ? "복사했어요" : copied === "fail" ? "복사 실패 · 질문을 선택해 복사하세요" : "질문 복사하기"}</button><span className="sr-only" role="status">{copied === "done" ? "실제 인터뷰 질문을 복사했습니다." : copied === "fail" ? "클립보드에 복사하지 못했습니다." : ""}</span></div>
    </section>

    <details className="rounded-card border border-card bg-base p-5"><summary className="cursor-pointer text-sm font-semibold">분석 항목과 근거 전체 보기</summary><div className="mt-4 grid gap-5 md:grid-cols-2">{Object.entries(report.sections).map(([section, rows]) => <section key={section}><h3 className="mb-2 text-sm font-semibold text-brand">{SECTION_LABELS[section] || section}</h3>{rows.length ? rows.map((insight, index) => <div key={index} className="mb-3"><InsightContent insight={insight} sources={sources} /></div>) : <p className="text-sm text-muted">저장된 분석 없음</p>}</section>)}</div></details>

    <div className="flex flex-wrap items-center gap-3"><p className="min-w-0 flex-1 text-[13px] leading-[1.65] text-muted">AI 페르소나 {people.length}명과 나눈 대화를 정리한 것입니다. 실제 고객 답변이나 구매 의사 확정이 아닙니다.</p><button type="button" onClick={onContinue} data-report-controls className="h-[46px] rounded-btn border border-btn-border bg-base px-[18px] text-sm text-ink-2">대화 이어가기</button><button type="button" onClick={onNewTargets} data-report-controls className="h-[46px] rounded-btn bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-hover">다른 타깃과 다시 해보기</button></div>
    <p className={`${styles.printOnly} text-xs`}>근거 발화 원문과 전체 분석은 JSON 또는 텍스트 내려받기에서 확인할 수 있습니다. 실제 고객 인터뷰로 검증해야 하는 AI 시뮬레이션 가설입니다.</p>
  </main>;
}
