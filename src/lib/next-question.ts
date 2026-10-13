import { api, type NextQuestionRecommendation } from "./soul-api";

export type QuestionRequestContext = {
  sessionId: string;
  threadId: string;
  transcriptLength: number;
  publicRevision: number;
  draftVersion: number;
  targetVersion: number;
};

/** A recommendation is never a session mutation or an automatically sent message. */
export function loadNextQuestion(sessionId: string, revision: number, signal?: AbortSignal) {
  return api<NextQuestionRecommendation>(`/sessions/${encodeURIComponent(sessionId)}/next-question`, { revision }, signal);
}

/** Ignore late responses after the conversation or the user's input has changed. */
export function sameQuestionContext(requested: QuestionRequestContext, current: QuestionRequestContext, selectedSessionId: string | null) {
  return (selectedSessionId === null || selectedSessionId === requested.sessionId)
    && requested.sessionId === current.sessionId
    && requested.threadId === current.threadId
    && requested.transcriptLength === current.transcriptLength
    && requested.publicRevision === current.publicRevision;
}

export function canFillQuestionDraft(requested: QuestionRequestContext, current: QuestionRequestContext, selectedSessionId: string | null) {
  return sameQuestionContext(requested, current, selectedSessionId)
    && requested.draftVersion === current.draftVersion
    && requested.targetVersion === current.targetVersion;
}
