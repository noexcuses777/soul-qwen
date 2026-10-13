export type ReportStance = "unknown" | "conditional" | "positive" | "negative";

export interface ReportInsight {
  text: string;
  utterance_ids: string[];
  evidence_ids: string[];
  hypothesis: true;
  confidence: "low" | "medium" | "high";
  evidence_level: number;
  section?: string;
}

export interface ReportSource {
  id: string;
  persona_id: string;
  name: string;
  phase: string;
  content: string;
  reason: string;
  stance: ReportStance;
  evidence_ids: string[];
  quality_flags: string[];
  generated_content?: string | null;
}

export interface ReportPosition {
  persona_id: string;
  name: string;
  segment: string;
  stance: ReportStance;
  stance_label: string;
  content: string;
  reason: string;
  utterance_id: string | null;
  evidence_ids: string[];
  quality_flags: string[];
}

export interface ReportTopic {
  id: string;
  question: string;
  utterance_ids: string[];
  positions: ReportPosition[];
  insights: ReportInsight[];
}

export interface ReportChange {
  persona_id: string;
  name: string;
  topic_id: string;
  question: string;
  before: Pick<ReportPosition, "utterance_id" | "stance" | "stance_label" | "content" | "reason">;
  after: Pick<ReportPosition, "utterance_id" | "stance" | "stance_label" | "content" | "reason">;
  basis: string;
  utterance_ids: string[];
}

export interface ReportFollowup {
  question: string;
  topic_id: string | null;
  persona_id: string | null;
  utterance_ids: string[];
  kind: "suggestion" | "clarification" | "peer_condition" | "real_world_check";
  why: string;
}

export interface SoulReportView {
  meta: {
    session_id: string;
    generated_at: string | null;
    revision: number;
    revision_inferred: boolean;
    stale: boolean;
    persona_count: number;
    question_count: number;
    public_turn_count: number;
    insight_count: number;
    change_count: number;
    unknown_count: number;
    excluded_insight_count: number;
    participants: { id: string; name: string; segment: string }[];
    metrics_notice: string;
  };
  notice: string;
  conclusion: ReportInsight[];
  topics: ReportTopic[];
  new_insights: ReportInsight[];
  changes: ReportChange[];
  followups: ReportFollowup[];
  unknowns: { text: string; utterance_ids: string[]; evidence_ids: string[] }[];
  real_interview: ReportInsight[];
  sections: Record<string, ReportInsight[]>;
  sources: ReportSource[];
  audits?: Record<string, unknown>[];
}
