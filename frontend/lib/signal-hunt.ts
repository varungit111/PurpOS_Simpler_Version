import { z } from "zod";
import { API_BASE_URL } from "./api-config";

export const pestleCategorySchema = z.enum([
  "political",
  "economic",
  "social",
  "technological",
  "legal",
  "environmental"
]);

export const signalHuntDecisionSchema = z.enum([
  "unplaced",
  "ignore",
  "watch",
  "opportunity",
  "threat"
]);

export const pestleEvidenceSourceSchema = z.object({
  id: z.string().uuid().nullable(),
  title: z.string().min(1),
  sourceType: z.string().min(1),
  url: z.string().url().nullable(),
  summary: z.string().min(1).nullable()
});

export const pestleFindingSchema = z.object({
  id: z.string().uuid(),
  category: pestleCategorySchema,
  signal: z.string().min(1),
  description: z.string().min(1),
  whyItMatters: z.string().min(1),
  opportunityOrRisk: z.string().min(1),
  evidenceSources: z.array(pestleEvidenceSourceSchema),
  decision: signalHuntDecisionSchema,
  impact: z.number().int().min(0).max(100).nullable(),
  urgency: z.number().int().min(0).max(100).nullable()
});

const signalHuntProgressSchema = z.object({
  findingsCount: z.number().int().nonnegative(),
  categoriesCovered: z.array(pestleCategorySchema),
  totalCategories: z.number().int().positive(),
  label: z.string().min(1)
});

const signalHuntResponseSchema = z.object({
  activity_id: z.literal("signal-hunt"),
  ai_status: z.enum(["idle", "connected", "unavailable", "error"]),
  progress: signalHuntProgressSchema,
  findings: z.array(pestleFindingSchema),
  message: z.string().min(1).nullable()
});

export type PESTLECategory = z.infer<typeof pestleCategorySchema>;
export type SignalHuntDecision = z.infer<typeof signalHuntDecisionSchema>;
export type PESTLEFinding = z.infer<typeof pestleFindingSchema>;
export type SignalHuntProgress = z.infer<typeof signalHuntProgressSchema>;
export type SignalHuntResponse = z.infer<typeof signalHuntResponseSchema>;

export const pestleCategoryLabels: Record<PESTLECategory, string> = {
  political: "Political",
  economic: "Economic",
  social: "Social",
  technological: "Technological",
  legal: "Legal",
  environmental: "Environmental"
};

export const signalHuntDecisionLabels: Record<SignalHuntDecision, string> = {
  unplaced: "Unplaced",
  ignore: "Ignore",
  watch: "Watch",
  opportunity: "Opportunity",
  threat: "Threat"
};

export async function getSignalHunt(
  sessionId: string
): Promise<SignalHuntResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/signal-hunt`
  );

  if (!response.ok) {
    throw new Error("Unable to load Signal Hunt.");
  }

  return signalHuntResponseSchema.parse(await response.json());
}

export async function generateSignalHuntFindings(
  sessionId: string
): Promise<SignalHuntResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/signal-hunt/generate`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    throw new Error("Unable to generate Signal Hunt findings.");
  }

  return signalHuntResponseSchema.parse(await response.json());
}

export async function saveSignalHuntFindings({
  sessionId,
  findings
}: {
  sessionId: string;
  findings: PESTLEFinding[];
}): Promise<SignalHuntResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/signal-hunt`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ findings })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Signal Hunt findings.");
  }

  return signalHuntResponseSchema.parse(await response.json());
}
