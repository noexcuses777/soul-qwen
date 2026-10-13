/** SOUL uses only the preserved Qwen backend. No client-side model fallback. */
import { normalize } from "./korean-text";
export const SESSION_KEY = "soul.qwen.session.v1";
export const SESSION_EVENT = "soul:qwen-session";
export type Evidence = { source_id: string; text: string; level: 0 | 1 | 2 | 3 | 4; consent_note: string };
export type IdeaInput = { q1: string; q2: string; q3: string; q3_1: string; q3_2: string; q4_1: string; q5: string; customer_type: "개인 고객에게 팝니다" | "기업·기관에 팝니다" | "아직 모르겠어요"; founder_strength: string; evidence: Evidence[] };
export type Target = { display_name?: string; id: string; segment_name: string; why_relevant: string; problem_exposure: string; expected_current_alternative: string; buying_role: string; critical_unknowns: string[]; confidence: "low" | "medium" | "high"; evidence_level: number; evidence_ids: string[]; relevance: number };
export type ReasoningRule = { id: string; trigger: string; value: string; tradeoff: string; conditional_choice: string; basis_fields: string[]; evidence_ids: string[]; unknowns: string[]; kind: "hypothesis" };
export type PersonaCard = { id: string; presentation: { display_name: string; fictional: true }; session_state: PersonaState; immutable_core: {
  identity_context: Record<string, string> & { segment: string; use_context: string };
  problem_context: { current_alternative: string; problem_severity: string; frequency: string; trigger: string; workaround: string; past_failed_attempts: string[] };
  decision_model: { adoption_barrier: string; buying_role: string; switching_cost: string; budget_constraint: string; decision_criteria: string[]; risk_sensitivity: string; decision_authority: string; must_have: string[]; rejection_conditions: string[] };
  goals_motivations: Record<string, string>;
  evidence_anchors: { source_id: string; field: string; quote: string; level: number }[];
  interaction_style: Record<string, string>;
  stable_profile: { core_values: string[]; stable_constraints: string[]; stable_preferences: string[]; key_history: string[] };
  reasoning_rules: ReasoningRule[];
  timeline: { source_id: string; event_quote: string; when: string }[];
  hypothesis: true;
} };
export type PersonaState = { stance: "unknown" | "conditional" | "positive" | "negative"; reasons: string[]; unresolved_issues: string[]; revisions: string[] };
export type Utterance = { id: string; persona_id: string; phase: "pre" | "group" | "post" | "independent" | "generic"; round: string; question: string; content: string; stance: PersonaState["stance"]; reason: string; unresolved_issues: string[]; evidence_ids: string[]; reply_to: string | null; thread_id: string | null; addressed_to: string | null; quality_flags: string[]; followup_question: string; reasoning_rule_ids: string[] };
export type Insight = { text: string; utterance_ids: string[]; evidence_ids: string[]; hypothesis: true; confidence: string; evidence_level: number };
export type SoulSession = { id: string; input: IdeaInput; brief: Record<string, string | string[]>; targets: Target[]; target_display_names?: Record<string, string>; cards: PersonaCard[]; selected_target_ids?: string[]; validations: { issues: { kind: string; detail: string }[]; advisory: { kind: string; detail: string }[] }[]; transcript: Utterance[]; states: Record<string, PersonaState>; status: string; lounge_mode?: string | null; mode: "qwen" | "mock"; error: string | null; pending_question: string | null; pending_speaker: string | null; report: { sections: Record<string, Insight[]>; notice: string } | null; report_revision: number | null; report_stale: boolean; report_generated_at?: string | null; suggestions: { id: string; question: string; topic: string; why: string; persona_id: string | null }[]; threads: { id: string; question: string; utterance_ids: string[]; status: string; remaining_issues: string[]; stop_reason: string }[]; chat_events: { before: number; role: string; content: string }[]; dialogue_runtime: { followup?: { key: [string, string | null, "auto" | "direct" | "interactive"]; done: boolean }; report_snapshot?: { done: boolean } }; usage: Record<string, unknown> };
export type InputLimits = Record<string, number>;
export type NextQuestionRecommendation = { status: "discussion" | "needs_evidence" | "no_new_question"; question: string; why: string; source_utterance_ids: string[]; missing_information: string[]; id: string; revision: number };
export const DEFAULT_LIMITS: InputLimits = { q1: 200, q2: 1000, q3: 1500, q3_1: 1500, q3_2: 600, q4_1: 1000, founder_strength: 600, evidence_text: 1500, evidence_total: 6000, evidence_count: 8, target_field: 300, question: 500 };
export function known(value?: string | null) { return value && value !== "UNKNOWN" ? normalize(value) : "아직 확인하지 못했어요"; }
export function rememberSession(session: SoulSession) {
  if (typeof window !== "undefined") {
    try { localStorage.setItem(SESSION_KEY, session.id); } catch { /* Storage may be disabled; live UI still works. */ }
    window.dispatchEvent(new CustomEvent(SESSION_EVENT, { detail: session }));
  }
  return session;
}
export function currentSessionId() { if (typeof window === "undefined") return null; try { return localStorage.getItem(SESSION_KEY); } catch { return null; } }
export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) { super(message); this.name = "ApiError"; this.status = status; }
}
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { method: body === undefined ? "GET" : "POST", headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal, cache: "no-store" });
  let payload: unknown;
  try { payload = await response.json(); } catch { throw new Error(`서버 응답을 읽지 못했습니다 (${response.status}). 백엔드 연결을 확인해 주세요.`); }
  if (!response.ok) {
    const detail = (payload as { detail?: unknown }).detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail ?? payload);
    throw new ApiError(response.status === 409 ? `진행 중인 작업을 먼저 마쳐 주세요. ${message}` : message, response.status);
  }
  return payload as T;
}
export async function getSession(id: string, signal?: AbortSignal) { return api<SoulSession>(`/sessions/${encodeURIComponent(id)}`, undefined, signal); }
export async function getCurrentSession(signal?: AbortSignal) {
  const id = currentSessionId();
  if (id) { try { const session = await getSession(id, signal); return currentSessionId() === id ? rememberSession(session) : session; } catch (error) { if (signal?.aborted) throw error; if (!(error instanceof ApiError) || error.status !== 404) throw error; } }
  const session = await api<SoulSession | null>("/latest", undefined, signal);
  return session && currentSessionId() === id ? rememberSession(session) : session;
}
export async function createSession(input: IdeaInput) { return rememberSession(await api<SoulSession>("/sessions", input)); }
function publishOperation(session: SoulSession, activeId: string | null) {
  const currentId = currentSessionId();
  if (activeId === null ? currentId !== null && currentId !== session.id : currentId !== activeId || activeId !== session.id) return false;
  rememberSession(session); return true;
}
export async function sessionAction(id: string, action: string, body: unknown = {}) {
  const activeId = currentSessionId();
  const session = await api<SoulSession>(`/sessions/${encodeURIComponent(id)}/${action}`, body);
  publishOperation(session, activeId); return session;
}
/** Poll only persisted completed utterances. This is not simulated token streaming. */
export async function runSessionAction(id: string, action: string, body: unknown = {}, onProgress?: (session: SoulSession) => void) {
  let reading = false;
  let active = true;
  const activeId = currentSessionId();
  const timer = setInterval(async () => {
    if (reading) return;
    reading = true;
    try { const s = await getSession(id); if (active && publishOperation(s, activeId)) onProgress?.(s); } catch { /* The mutation's final response carries actionable errors. */ }
    finally { reading = false; }
  }, 1200);
  try {
    const s = await api<SoulSession>(`/sessions/${encodeURIComponent(id)}/${action}`, body);
    active = false; clearInterval(timer);
    if (publishOperation(s, activeId)) onProgress?.(s); return s;
  } catch (error) {
    active = false; clearInterval(timer);
    try { const partial = await getSession(id); if (publishOperation(partial, activeId)) onProgress?.(partial); } catch {}
    throw error;
  } finally { active = false; clearInterval(timer); }
}
