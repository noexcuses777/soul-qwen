"use client";
import { useState } from "react";
import { sessionAction, type PersonaCard } from "@/lib/soul-api";
export function PersonaEditor({ sessionId, initial, onDone, onCancel }: { sessionId: string; initial: PersonaCard; onDone: () => void; onCancel: () => void }) {
  const [card, setCard] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fields = [{ label: "요즘 상황", block: "identity_context", field: "use_context" }, { label: "현재 대안", block: "problem_context", field: "current_alternative" }, { label: "도입할 때 걸리는 점", block: "decision_model", field: "adoption_barrier" }] as const;
  async function save() {
    if (busy) return;
    setBusy(true); setError("");
    try { await sessionAction(sessionId, `cards/${card.id}`, { ...card, presentation: { ...card.presentation, display_name: card.presentation.display_name.trim() } }); onDone(); }
    catch (err) { setError(err instanceof Error ? err.message : "저장하지 못했습니다."); }
    finally { setBusy(false); }
  }
  return <form className="flex flex-col gap-5" onSubmit={event => { event.preventDefault(); void save(); }}>
    <label className="flex flex-col gap-1.5 text-sm font-medium">이름<input required maxLength={24} value={card.presentation.display_name} onChange={event => setCard(previous => ({ ...previous, presentation: { ...previous.presentation, display_name: event.target.value } }))} className="h-11 rounded-[11px] border border-input-border bg-input px-3.5" /></label>
    <p className="text-sm text-muted">{card.immutable_core.identity_context.segment}</p>
    {fields.map(row => <label key={row.field} className="flex flex-col gap-1.5 text-sm font-medium">{row.label}<textarea maxLength={300} rows={3} value={String((card.immutable_core[row.block] as unknown as Record<string, unknown>)[row.field]) === "UNKNOWN" ? "" : String((card.immutable_core[row.block] as unknown as Record<string, unknown>)[row.field])} onChange={event => setCard(previous => ({ ...previous, immutable_core: { ...previous.immutable_core, [row.block]: { ...previous.immutable_core[row.block], [row.field]: event.target.value || "UNKNOWN" } } }))} className="rounded-[11px] border border-input-border bg-input px-3.5 py-3 font-normal leading-relaxed" /></label>)}
    {error && <p role="alert" className="text-sm text-conflict-fg">{error}</p>}
    <div className="flex justify-end gap-2"><button type="button" disabled={busy} onClick={onCancel} className="h-11 rounded-btn border border-btn-border px-4 text-sm">취소</button><button type="submit" disabled={busy} className="h-11 rounded-btn bg-brand px-5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "확인 중…" : "저장하기"}</button></div>
  </form>;
}
