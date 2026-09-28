import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const evidenceWallCardSchema = z.object({
  id: z.string().uuid(),
  sourceActivity: z.string().min(1).nullable(),
  sourceLabel: z.string().min(1),
  claim: z.string().min(1),
  summary: z.string().min(1).nullable(),
  cardType: z.enum(["strength", "tension", "touch-point", "fact"]),
  coverageAreaIds: z.array(z.string().min(1)),
  evidenceStatus: z.enum(["user-confirmed", "source-derived", "ai-inferred"]),
  sourceReference: z.string().min(1).nullable(),
  derivedFromEvidenceIds: z.array(z.string().uuid())
});

const evidenceWallCoverageAreaSchema = z.object({
  areaId: z.string().min(1),
  label: z.string().min(1),
  question: z.string().min(1),
  status: z.enum(["uncovered", "partial", "sufficient"]),
  evidenceCount: z.number().int().nonnegative()
});

const evidenceWallGroupSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  status: z.enum(["uncovered", "partial", "sufficient"]),
  evidenceCount: z.number().int().nonnegative(),
  cards: z.array(evidenceWallCardSchema)
});

const identifyThemeSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  summary: z.string().min(1),
  evidence_ids: z.array(z.string().uuid())
});

const evidenceWallResponseSchema = z.object({
  activity_id: z.literal("evidence-wall"),
  evidenceCount: z.number().int().nonnegative(),
  coverageAreas: z.array(evidenceWallCoverageAreaSchema),
  groups: z.array(evidenceWallGroupSchema),
  selectedThemes: z.array(identifyThemeSchema),
  message: z.string().min(1).nullable()
});

export type EvidenceWallCard = z.infer<typeof evidenceWallCardSchema>;
export type EvidenceWallCoverageArea = z.infer<
  typeof evidenceWallCoverageAreaSchema
>;
export type EvidenceWallGroup = z.infer<typeof evidenceWallGroupSchema>;
export type EvidenceWallResponse = z.infer<typeof evidenceWallResponseSchema>;

export async function getEvidenceWall(
  sessionId: string
): Promise<EvidenceWallResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/evidence-wall`
  );

  if (!response.ok) {
    throw new Error("Unable to load Evidence Wall.");
  }

  return evidenceWallResponseSchema.parse(await response.json());
}

export async function saveEvidenceWallThemes({
  sessionId,
  selectedGroupIds
}: {
  sessionId: string;
  selectedGroupIds: string[];
}): Promise<EvidenceWallResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/evidence-wall`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ selectedGroupIds })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Evidence Wall synthesis.");
  }

  return evidenceWallResponseSchema.parse(await response.json());
}
