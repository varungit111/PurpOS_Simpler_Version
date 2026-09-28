import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const activityProgressSchema = z.object({
  current: z.number().int().nonnegative(),
  total: z.number().int().positive(),
  label: z.string().min(1)
});

const identifyEvidenceUpdateSchema = z.object({
  id: z.string().uuid(),
  source: z.object({
    id: z.string().uuid(),
    title: z.string().min(1),
    source_type: z.string().min(1),
    url: z.string().url().nullable(),
    captured_at: z.string()
  }),
  claim: z.string().min(1),
  summary: z.string().nullable(),
  confidence: z.number().nullable()
});

const activityConversationResponseSchema = z.object({
  session_id: z.string().uuid(),
  activity_id: z.string().min(1),
  assistant_message: z.string().min(1),
  activity_status: z.string().min(1),
  progress: activityProgressSchema,
  evidence_updates: z.array(identifyEvidenceUpdateSchema),
  next_action: z.enum([
    "ask_question",
    "revisit_topic",
    "retrieve_evidence",
    "validate_output",
    "continue_stage"
  ]),
  ai_status: z.string().min(1)
});

export type ActivityConversationResponse = z.infer<
  typeof activityConversationResponseSchema
>;

export async function sendActivityMessage({
  sessionId,
  activityId,
  message
}: {
  sessionId: string;
  activityId: string;
  message: string;
}): Promise<ActivityConversationResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/conversation`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        activity_id: activityId,
        message
      })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to send Hot Seat message.");
  }

  return activityConversationResponseSchema.parse(await response.json());
}
