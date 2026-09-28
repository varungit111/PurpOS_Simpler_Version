import { z } from "zod";
import { API_BASE_URL } from "./api-config";

export const positioningEvidenceTopicSchema = z.enum([
  "who-served",
  "value-created",
  "current-positioning",
  "distinctiveness",
  "social-contribution",
  "current-vs-desired"
]);

export const positioningEvidenceResponseSchema = z.object({
  id: z.string().uuid(),
  topic: positioningEvidenceTopicSchema,
  prompt: z.string().min(1),
  response: z.string().min(1),
  supportingEvidence: z.array(z.string().min(1))
});

export const whereDoYouStandEvidenceSchema = z.object({
  id: z.string().uuid(),
  responses: z.array(positioningEvidenceResponseSchema),
  sourceActivity: z.literal("where-do-you-stand"),
  sourceLabel: z.string().min(1),
  collectedAt: z.string().min(1)
});

const whereDoYouStandProgressSchema = z.object({
  responseCount: z.number().int().nonnegative(),
  label: z.string().min(1)
});

const whereDoYouStandResponseSchema = z.object({
  activity_id: z.literal("where-do-you-stand"),
  progress: whereDoYouStandProgressSchema,
  evidence: whereDoYouStandEvidenceSchema.nullable(),
  message: z.string().min(1).nullable()
});

export type PositioningEvidenceResponse = z.infer<
  typeof positioningEvidenceResponseSchema
>;
export type WhereDoYouStandResponse = z.infer<
  typeof whereDoYouStandResponseSchema
>;

export async function getWhereDoYouStand(
  sessionId: string
): Promise<WhereDoYouStandResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/where-do-you-stand`
  );

  if (!response.ok) {
    throw new Error("Unable to load Where Do You Stand.");
  }

  return whereDoYouStandResponseSchema.parse(await response.json());
}

export async function saveWhereDoYouStand({
  sessionId,
  responses
}: {
  sessionId: string;
  responses: PositioningEvidenceResponse[];
}): Promise<WhereDoYouStandResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/where-do-you-stand`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ responses })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Where Do You Stand.");
  }

  return whereDoYouStandResponseSchema.parse(await response.json());
}
