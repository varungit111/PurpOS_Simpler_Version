/**
 * Common shape for simple backend health responses.
 */
export interface HealthResponse {
  status: "ok";
  service: string;
}

export type ConversationRole = "assistant" | "user";

export type ConversationNextAction =
  | "ask_question"
  | "revisit_topic"
  | "retrieve_evidence"
  | "validate_output"
  | "continue_stage";

export type ActivityProgress = {
  current: number;
  total: number;
  label: string;
};

export type IdentifyEvidenceUpdate = {
  id: string;
  source: {
    id: string;
    title: string;
    source_type: string;
    url: string | null;
    captured_at: string;
  };
  claim: string;
  summary: string | null;
  confidence: number | null;
};

export type ActivityConversationResponse = {
  session_id: string;
  activity_id: string;
  assistant_message: string;
  activity_status: string;
  progress: ActivityProgress;
  evidence_updates: IdentifyEvidenceUpdate[];
  next_action: ConversationNextAction;
  ai_status: string;
};
