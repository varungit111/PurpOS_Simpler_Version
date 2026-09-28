import { z } from "zod";
import { API_BASE_URL } from "./api-config";

export const researchSourceTypeSchema = z.enum([
  "sme-provided",
  "uploaded-evidence",
  "configured-source",
  "public-website",
  "ai-synthesis"
]);

export const aiDetectiveClassificationSchema = z.enum([
  "correct",
  "wrong",
  "interesting",
  "investigate"
]);

export const researchFindingSchema = z.object({
  id: z.string().uuid(),
  topic: z.string().min(1),
  summary: z.string().min(1),
  sourceType: researchSourceTypeSchema,
  sourceLabel: z.string().min(1),
  sourceReference: z.string().min(1).nullable(),
  classification: aiDetectiveClassificationSchema,
  reviewNote: z.string().min(1).nullable(),
  collectedAt: z.string().min(1)
});

const aiDetectiveProgressSchema = z.object({
  findingsCount: z.number().int().nonnegative(),
  label: z.string().min(1),
  limitation: z.string().min(1).nullable()
});

const externalResearchDocumentSchema = z.object({
  id: z.string().min(1),
  sourceType: z.string().min(1),
  category: z.string().min(1),
  url: z.string().url(),
  title: z.string().min(1).nullable(),
  organisationDomain: z.string().min(1).nullable(),
  retrievedAt: z.string().min(1),
  status: z.string().min(1),
  statusReason: z.string().min(1).nullable(),
  content: z.string().min(1).nullable(),
  snippet: z.string().min(1).nullable(),
  contentHash: z.string().min(1).nullable()
});

const externalResearchCategorySchema = z.object({
  category: z.string().min(1),
  status: z.string().min(1),
  sourceIds: z.array(z.string().min(1)),
  message: z.string().min(1).nullable()
});

const externalResearchStateSchema = z.object({
  status: z.string().min(1),
  provider: z.string().min(1),
  updatedAt: z.string().min(1),
  documents: z.array(externalResearchDocumentSchema),
  categories: z.array(externalResearchCategorySchema),
  synthesisError: z.string().min(1).nullable()
});

const aiDetectiveResponseSchema = z.object({
  activity_id: z.literal("ai-detective"),
  research_status: z.enum([
    "idle",
    "limited",
    "unavailable",
    "not-configured",
    "retrieved",
    "connected",
    "error"
  ]),
  progress: aiDetectiveProgressSchema,
  findings: z.array(researchFindingSchema),
  externalResearch: externalResearchStateSchema,
  message: z.string().min(1).nullable()
});

export type ResearchFinding = z.infer<typeof researchFindingSchema>;
export type ResearchSourceType = z.infer<typeof researchSourceTypeSchema>;
export type AIDetectiveClassification = z.infer<
  typeof aiDetectiveClassificationSchema
>;
export type AIDetectiveProgress = z.infer<typeof aiDetectiveProgressSchema>;
export type ExternalResearchDocument = z.infer<
  typeof externalResearchDocumentSchema
>;
export type ExternalResearchCategory = z.infer<
  typeof externalResearchCategorySchema
>;
export type ExternalResearchState = z.infer<typeof externalResearchStateSchema>;
export type AIDetectiveResponse = z.infer<typeof aiDetectiveResponseSchema>;

export const researchSourceTypeLabels: Record<ResearchSourceType, string> = {
  "sme-provided": "SME provided",
  "uploaded-evidence": "Uploaded evidence",
  "configured-source": "Configured source",
  "public-website": "Public website",
  "ai-synthesis": "AI synthesis"
};

export const aiDetectiveClassificationLabels: Record<
  AIDetectiveClassification,
  string
> = {
  correct: "Correct",
  wrong: "Wrong",
  interesting: "Interesting",
  investigate: "Investigate"
};

export async function getAIDetective(
  sessionId: string
): Promise<AIDetectiveResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/ai-detective`
  );

  if (!response.ok) {
    throw new Error("Unable to load AI Detective.");
  }

  return aiDetectiveResponseSchema.parse(await response.json());
}

export async function collectAIDetectiveFindings(
  sessionId: string,
  options: { refresh?: boolean } = {}
): Promise<AIDetectiveResponse> {
  const query = options.refresh ? "?refresh=true" : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/ai-detective/collect${query}`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    throw new Error("Unable to collect AI Detective findings.");
  }

  return aiDetectiveResponseSchema.parse(await response.json());
}

export async function saveAIDetectiveFindings({
  sessionId,
  findings
}: {
  sessionId: string;
  findings: ResearchFinding[];
}): Promise<AIDetectiveResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/ai-detective`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ findings })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save AI Detective findings.");
  }

  return aiDetectiveResponseSchema.parse(await response.json());
}
