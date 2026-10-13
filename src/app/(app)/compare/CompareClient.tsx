"use client";
import Link from "next/link";
import { Chip } from "@/components/Chip";
import { PersonaAvatar } from "@/components/PersonaAvatar";
import { known, type PersonaCard } from "@/lib/soul-api";
import { useSoulSession } from "@/lib/use-soul-session";
import { cardColor, cardTargetId } from "@/lib/persona-presentation";
import { evidenceDescription, evidenceLabel } from "@/lib/evidence-presentation";
const SECONDARY = "inline-flex h-11 shrink-0 items-center justify-center rounded-btn border border-btn-border bg-base px-4 text-sm text-ink-2";
export function CompareClient() {
  const { session, loading, error: readError } = useSoulSession();
  if (loading) return <main className="p-20 text-ink-3" role="status">페르소나와 검사 결과를 불러오고 있어요.</main>;
  if (!session?.cards.length) return <main className="flex grow flex-col items-center justify-center gap-4 p-20"><h1 className="text-2xl font-semibold">먼저 이용자를 고르고 페르소나를 만들어 주세요</h1>{readError && <p role="alert">{readError}</p>}<Link href="/targets" className={SECONDARY}>이용자 고르기</Link></main>;
  const canEdit = session.status === "SELECTED";
  const cards = session.cards;
  const decisions = cards.map(card => ({ name: card.presentation.display_name, criterion: card.immutable_core.decision_model.decision_criteria.find(value => value && value !== "UNKNOWN") || card.immutable_core.reasoning_rules.find(rule => rule.value && rule.value !== "UNKNOWN")?.value }));
  const distinctDecisions = new Set(decisions.map(value => value.criterion).filter(Boolean)).size > 1;
  const rows: { label: string; render: (card: PersonaCard) => React.ReactNode; highlight?: boolean }[] = [
    { label: "요즘 상황", render: c => known(c.immutable_core.identity_context.use_context) },
    { label: "현재 대안", render: c => known(c.immutable_core.problem_context.current_alternative) },
    { label: "문제의 정도", render: c => known(c.immutable_core.problem_context.problem_severity) },
    { label: "바라는 결과", render: c => known(c.immutable_core.goals_motivations.desired_outcome) },
    { label: "판단 기준", render: c => c.immutable_core.decision_model.decision_criteria.length ? <div className="flex flex-wrap gap-1.5">{c.immutable_core.decision_model.decision_criteria.map((criterion, index) => <Chip key={index}>{criterion}</Chip>)}</div> : known(null) },
    { label: "도입 장벽", render: c => known(c.immutable_core.decision_model.adoption_barrier) },
    { label: "전환 비용", render: c => known(c.immutable_core.decision_model.switching_cost) },
    { label: "예산 조건", render: c => known(c.immutable_core.decision_model.budget_constraint) },
    { label: "선택의 논리", highlight: true, render: c => c.immutable_core.reasoning_rules.length ? c.immutable_core.reasoning_rules.map(rule => <div key={rule.id} className="mb-3 last:mb-0"><p className="font-medium">{rule.trigger}</p><p className="mt-1">{rule.value} · {rule.tradeoff}</p><p className="mt-1">{rule.conditional_choice}</p><p className="mt-1 text-xs text-muted">추론한 판단 조건 · 실제 경험 확인 전</p></div>) : known(null) },
    { label: "근거", render: c => c.immutable_core.evidence_anchors.length ? c.immutable_core.evidence_anchors.map((anchor, index) => <p key={index} title={evidenceDescription(anchor.level)}>{evidenceLabel(anchor.level)} · {anchor.source_id}: <q>{anchor.quote}</q></p>) : evidenceDescription(0) },
  ];
  return <>
    <main className="flex grow flex-col gap-[18px] px-[clamp(20px,5vw,70px)] pt-[30px] pb-6"><div className="flex flex-wrap items-end gap-4"><div className="grow"><p className="font-mono text-xs tracking-[0.14em] text-muted">STEP 03</p><h1 className="mt-2 text-[28px] font-bold tracking-[-0.022em]">고른 {cards.length}명, 한눈에 보기</h1><p className="mt-2 text-[15px] leading-[1.7] text-ink-3">나란히 놓고 보면 어디서 부딪힐지 미리 보여요. 어색한 부분은 지금 고치는 게 좋아요.</p></div><p className="rounded-[9px] bg-bubble px-3 py-2 text-xs text-ink-3">{session.mode === "mock" ? "모의 테스트 데이터 · 실제 Qwen 결과가 아닙니다" : "실제 사람이 아니라 AI가 만든 가상 인물이에요"}</p></div>
      {readError && <div role="alert" className="rounded-card bg-conflict-bg p-4 text-sm text-conflict-fg">{readError}</div>}

      <section className={`flex flex-col gap-[5px] rounded-[14px] px-5 py-4 ${distinctDecisions ? "bg-conflict-bg text-conflict-fg" : "bg-bubble text-ink-2"}`} aria-label="판단 기준 비교"><h2 className="text-sm font-semibold">{distinctDecisions ? "카드에 적힌 판단 조건이 서로 달라요" : "판단 기준은 대화에서 더 확인해 보세요"}</h2><p className="text-sm leading-[1.75]">{distinctDecisions ? decisions.filter(item => item.criterion).map(item => `${item.name}: ${item.criterion}`).join(" · ") : "현재 카드에 기록된 판단 기준만으로 의견 차이를 단정할 수 없어요. 같은 질문을 던져 차이를 확인해 보세요."}</p></section>

      <div className="overflow-x-auto rounded-card border border-card bg-base"><table className="w-full min-w-[760px] table-fixed border-collapse"><thead><tr><th className="w-[118px] bg-th p-4"/><>{cards.map(card => <th key={card.id} className="border-l border-divider px-[18px] py-4 text-left align-top"><div className="flex items-start gap-[11px]"><PersonaAvatar name={card.presentation.display_name} color={cardColor(session, card)} size="lg"/><div className="min-w-0 grow"><p className="text-[16px] font-semibold">{card.presentation.display_name}</p><p className="mt-1 text-xs font-normal leading-relaxed text-muted">{card.immutable_core.identity_context.segment}</p></div>{canEdit && <Link href={`/targets/new?edit=${encodeURIComponent(card.id)}&from=compare`} aria-label={`${card.presentation.display_name} 고치기`} className="inline-flex h-9 items-center rounded-[10px] border border-btn-border px-2 text-xs font-normal">고치기</Link>}</div></th>)}</></tr></thead><tbody>{rows.filter(row => row.label !== "근거" && (row.highlight || cards.some(card => row.render(card) !== known(null)))).map(row => <tr key={row.label} className="border-t border-divider"><th scope="row" className={`w-[118px] p-4 text-left align-top font-mono text-[11px] font-medium ${row.highlight ? "bg-action-bg text-brand" : "bg-th text-ink-3"}`}>{row.label}</th>{cards.map(card => <td key={card.id} className={`border-l border-divider px-[18px] py-4 align-top text-sm leading-[1.8] ${row.highlight ? "bg-hl" : "text-ink-2"}`}>{row.render(card)}</td>)}</tr>)}</tbody></table></div>
      <details className="rounded-card border border-card bg-base p-5"><summary className="cursor-pointer text-sm font-medium">추가 정보와 확인할 점</summary><div className="mt-3 flex flex-col gap-4">{cards.map((card, index) => <div key={card.id} className="text-sm leading-relaxed"><strong>{card.presentation.display_name}</strong><p className="mt-1">{(session.targets.find(target => target.id === cardTargetId(session, card))?.critical_unknowns.length ?? 0) > 0 ? session.targets.find(target => target.id === cardTargetId(session, card))!.critical_unknowns.join(" · ") : "추가로 확인할 조건이 아직 기록되지 않았습니다."}</p><div className="mt-2 text-xs text-muted">{card.immutable_core.evidence_anchors.length ? card.immutable_core.evidence_anchors.map((anchor, i) => <p key={i} title={evidenceDescription(anchor.level)}>{evidenceLabel(anchor.level)} · {anchor.source_id}: <q>{anchor.quote}</q></p>) : <p>실제 고객 자료로 확인하기 전의 AI 추론입니다.</p>}</div>{session.validations[index] && <div className="mt-2 text-muted"><p>{session.validations[index].issues.length ? session.validations[index].issues.map(issue => issue.detail).join(" · ") : "생성 검사 통과"}</p>{session.validations[index].advisory.map((advice, i) => <p key={i}>{advice.detail}</p>)}</div>}</div>)}</div></details>
    </main><footer className="flex shrink-0 flex-wrap items-center gap-3 border-t border-line bg-base px-[clamp(20px,5vw,70px)] py-5"><Link href="/targets" className={SECONDARY}>이용자 목록 보기</Link><p className="grow text-sm text-muted">채팅창에서 질문하면 각자가 답하고 서로의 조건을 비교해요.</p><Link href="/chat" className="inline-flex h-12 shrink-0 items-center rounded-btn bg-brand px-[26px] text-[15px] font-semibold text-white">대화 시작하기</Link></footer>

  </>;
}
