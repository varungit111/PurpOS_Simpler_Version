import { z } from "zod";
import { API_BASE_URL } from "./api-config";

// FastAPI serializes Python UUID values in this canonical shape, including
// legacy values whose version/variant bits are not RFC-constrained.
const backendUuidSchema = z
  .string()
  .regex(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

export const perceptionGapResolutionSchema = z.enum([
  "unresolved",
  "confirmed",
  "corrected",
  "clarified"
]);

export const evidenceReferenceSchema = z.object({
  id: backendUuidSchema,
  sourceType: z.string().min(1),
  label: z.string().min(1),
  detail: z.string().min(1).nullable()
});

export const perceptionGapSchema = z.object({
  id: backendUuidSchema,
  topic: z.string().min(1),
  perspectiveA: z.string().min(1),
  perspectiveB: z.string().min(1),
  difference: z.string().min(1),
  supportingEvidenceIds: z.array(backendUuidSchema).min(1),
  clarificationNeeded: z.boolean(),
  resolution: perceptionGapResolutionSchema,
  resolutionNote: z.string().min(1).nullable()
});

const perceptionGapProgressSchema = z.object({
  gapCount: z.number().int().nonnegative(),
  evidenceSourceCount: z.number().int().nonnegative(),
  requiredSourceCount: z.number().int().positive(),
  label: z.string().min(1)
});

const perceptionGapsResponseSchema = z.object({
  activity_id: z.literal("perception-gaps"),
  activity_status: z.enum(["locked", "available"]),
  dependency_message: z.string().min(1).nullable(),
  progress: perceptionGapProgressSchema,
  evidenceReferences: z.array(evidenceReferenceSchema),
  suggestedGaps: z.array(perceptionGapSchema),
  gaps: z.array(perceptionGapSchema),
  message: z.string().min(1).nullable()
});

export type EvidenceReference = z.infer<typeof evidenceReferenceSchema>;
export type PerceptionGap = z.infer<typeof perceptionGapSchema>;
export type PerceptionGapResolution = z.infer<
  typeof perceptionGapResolutionSchema
>;
export type PerceptionGapsResponse = z.infer<typeof perceptionGapsResponseSchema>;

export async function getPerceptionGaps(
  sessionId: string
): Promise<PerceptionGapsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/perception-gaps`
  );

  if (!response.ok) {
    throw new Error("Unable to load Perception Gaps.");
  }

  return perceptionGapsResponseSchema.parse(await response.json());
}

export async function savePerceptionGaps({
  sessionId,
  gaps
}: {
  sessionId: string;
  gaps: PerceptionGap[];
}): Promise<PerceptionGapsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/perception-gaps`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ gaps })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Perception Gaps.");
  }

  return perceptionGapsResponseSchema.parse(await response.json());
}

export async function reviewPerceptionGap({
  sessionId,
  gapId,
  resolution,
  perspectiveA,
  perspectiveB,
  difference,
  clarificationNeeded,
  resolutionNote
}: {
  sessionId: string;
  gapId: string;
  resolution: PerceptionGapResolution;
  perspectiveA?: string;
  perspectiveB?: string;
  difference?: string;
  clarificationNeeded?: boolean;
  resolutionNote?: string;
}): Promise<PerceptionGapsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/perception-gaps/${gapId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resolution,
        perspectiveA,
        perspectiveB,
        difference,
        clarificationNeeded,
        resolutionNote
      })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to review Perception Gap.");
  }

  return perceptionGapsResponseSchema.parse(await response.json());
}
