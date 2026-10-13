/** Fictional display labels only. Never fabricate biography or model evidence. */
import { known, type PersonaCard, type SoulSession, type Target } from "./soul-api";
import type { Persona, PersonaColor } from "./types";

export function presentationColor(id: string): PersonaColor {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return (hash % 5 + 1) as PersonaColor;
}
export function cardTargetId(session: Pick<SoulSession, "cards" | "targets" | "selected_target_ids">, card: PersonaCard) {
  const index = session.cards.findIndex(value => value.id === card.id);
  return session.selected_target_ids?.[index] ?? session.targets.find(t => t.segment_name === card.immutable_core.identity_context.segment)?.id ?? card.id;
}
export function cardColor(session: Pick<SoulSession, "cards" | "targets" | "selected_target_ids">, card: PersonaCard) {
  return presentationColor(cardTargetId(session, card));
}
export function targetPersonas(session: Pick<SoulSession, "cards" | "targets" | "selected_target_ids" | "target_display_names">, targets: Target[]): Persona[] {
  // Names are randomized once by the backend and stored on the session. Rendering,
  // filtering, card selection and reloads must never generate a different identity.
  const named = new Map(targets.map(t => [t.id, session.cards.find(card => cardTargetId(session, card) === t.id)?.presentation.display_name || t.display_name?.trim() || session.target_display_names?.[t.id] || ""]));
  const used = new Set([...named.values()].filter(Boolean));
  for (const [index, target] of targets.entries()) {
    if (named.get(target.id)) continue;
    const originalIndex = session.targets.findIndex(value => value.id === target.id);
    // Neutral recovery label for offline legacy drafts, rather than a fixed name pool.
    const base = `참여자 ${(originalIndex >= 0 ? originalIndex : index) + 1}`;
    let name = base;
    let suffix = 2;
    while (used.has(name)) name = `${base} (${suffix++})`;
    named.set(target.id, name); used.add(name);
  }
  return targets.map(target => ({ id: target.id, name: named.get(target.id)!, segment: target.segment_name,
    situation: known(target.problem_exposure), interests: [], worries: [],
    checkpoint: target.critical_unknowns.join(" · "), criticalUnknowns: target.critical_unknowns,
    evidenceLevel: target.evidence_level, reason: known(target.why_relevant),
    notes: known(target.expected_current_alternative), color: presentationColor(target.id),
    source: target.id.startsWith("custom-") ? "custom" : target.display_name ? "edited" : "recommended" }));
}
export function selectionPayload(picked: Target[], custom: Target[], personas: Persona[]) {
  const edited = new Set(custom.map(target => target.id));
  return { target_ids: picked.filter(target => !edited.has(target.id)).map(target => target.id),
    custom_targets: picked.filter(target => edited.has(target.id)).map(target => {
      const modelTarget = { ...target }; delete modelTarget.display_name;
      return modelTarget;
    }), display_names: Object.fromEntries(picked.map(target => [target.id, personas.find(p => p.id === target.id)?.name ?? ""])) };
}
