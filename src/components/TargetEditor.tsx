"use client";
import { useState } from "react";
import type { Target } from "@/lib/soul-api";
export const NEW_TARGET: Target = { id: "", segment_name: "", why_relevant: "", problem_exposure: "UNKNOWN", expected_current_alternative: "UNKNOWN", buying_role: "UNKNOWN", critical_unknowns: [], confidence: "low", evidence_level: 0, evidence_ids: [], relevance: 0.5 };
export const customTargetsKey = (id: string) => `soul.qwen.custom-targets.v1:${id}`;
export function loadCustomTargets(id: string): Target[] { try { const value = JSON.parse(localStorage.getItem(customTargetsKey(id)) ?? "[]"); return Array.isArray(value) ? value : []; } catch { return []; } }
export function saveCustomTargets(id: string, targets: Target[]) { localStorage.setItem(customTargetsKey(id), JSON.stringify(targets)); }
export function TargetEditor({ initial = NEW_TARGET, onSave, onCancel, onChange }: { initial?: Target; onSave: (target: Target) => void; onCancel?: () => void; onChange?: (target: Target) => void }) {
  const [target, setTarget] = useState(initial);
  function update(next: Target) { setTarget(next); onChange?.(next); }
  const rows: { key: "segment_name" | "why_relevant" | "problem_exposure" | "expected_current_alternative" | "buying_role"; label: string; required?: boolean }[] = [{ key: "segment_name", label: "어떤 이용자인가요? 사람·기관의 유형", required: true }, { key: "why_relevant", label: "이 이용자에게 물어볼 이유", required: true }, { key: "problem_exposure", label: "문제를 겪는 상황" }, { key: "expected_current_alternative", label: "현재 쓰는 대안" }, { key: "buying_role", label: "구매 과정에서의 조건 · 선택" }];
  return <form className="flex flex-col gap-4" onSubmit={event => { event.preventDefault(); if (target.segment_name.trim() && target.why_relevant.trim() && target.display_name?.trim()) onSave({ ...target, id: target.id || `custom-${Date.now()}`, segment_name: target.segment_name.trim(), why_relevant: target.why_relevant.trim(), display_name: target.display_name.trim() }); }}>
    <h2 className="text-[16px] font-semibold">어떤 사람인가요</h2>
    <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">이름<input required maxLength={24} value={target.display_name ?? ""} onChange={event => update({ ...target, display_name: event.target.value })} className="h-11 rounded-[11px] border border-input-border bg-input px-3.5 font-normal" /></label>
    <span className="-mt-2 self-end text-xs text-muted">{(target.display_name ?? "").length} / 24자</span>
    {rows.map(row => <label key={row.key} className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">{row.label}{row.required ? " *" : ""}<textarea value={target[row.key] === "UNKNOWN" ? "" : target[row.key]} maxLength={300} rows={row.key === "segment_name" ? 1 : 2} required={row.required} onChange={event => update({ ...target, [row.key]: event.target.value || (row.required ? "" : "UNKNOWN") })} className="w-full rounded-[11px] border border-input-border bg-input px-3.5 py-3 font-normal leading-relaxed" /><span className="self-end text-xs font-normal text-muted">{target[row.key] === "UNKNOWN" ? 0 : target[row.key].length} / 300자</span></label>)}
    <p className="text-xs leading-relaxed text-muted">모르는 조건은 비워두세요.</p>
    <div className="flex justify-end gap-2">{onCancel && <button type="button" onClick={onCancel} className="h-11 rounded-btn border border-btn-border px-4 text-sm">취소</button>}<button type="submit" className="h-11 rounded-btn bg-brand px-5 text-sm font-semibold text-white">저장하기</button></div>
  </form>;
}
