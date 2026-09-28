import { z } from "zod";
import { API_BASE_URL } from "./api-config";

export const companyCardSelectionStateSchema = z.enum(["current", "desired"]);

export const companyCardSelectionSchema = z.object({
  cardId: z.string().min(1),
  state: companyCardSelectionStateSchema
});

export const companyCardsEvidenceSchema = z.object({
  id: z.string().uuid(),
  selections: z.array(companyCardSelectionSchema),
  explanation: z.string().min(1).nullable(),
  sourceActivity: z.literal("company-cards"),
  sourceLabel: z.string().min(1),
  collectedAt: z.string().min(1)
});

const companyCardsProgressSchema = z.object({
  currentCount: z.number().int().nonnegative(),
  desiredCount: z.number().int().nonnegative(),
  label: z.string().min(1)
});

const companyCardsResponseSchema = z.object({
  activity_id: z.literal("company-cards"),
  content_status: z.literal("prototype-config"),
  progress: companyCardsProgressSchema,
  evidence: companyCardsEvidenceSchema.nullable(),
  message: z.string().min(1).nullable()
});

export type CompanyCardSelectionState = z.infer<
  typeof companyCardSelectionStateSchema
>;
export type CompanyCardsEvidence = z.infer<typeof companyCardsEvidenceSchema>;
export type CompanyCardsProgress = z.infer<typeof companyCardsProgressSchema>;
export type CompanyCardsResponse = z.infer<typeof companyCardsResponseSchema>;

export async function getCompanyCards(
  sessionId: string
): Promise<CompanyCardsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/company-cards`
  );

  if (!response.ok) {
    throw new Error("Unable to load Company Cards.");
  }

  return companyCardsResponseSchema.parse(await response.json());
}

export async function saveCompanyCards({
  sessionId,
  currentCardIds,
  desiredCardIds,
  explanation
}: {
  sessionId: string;
  currentCardIds: string[];
  desiredCardIds: string[];
  explanation: string | null;
}): Promise<CompanyCardsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/company-cards`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        currentCardIds,
        desiredCardIds,
        explanation
      })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Company Cards.");
  }

  return companyCardsResponseSchema.parse(await response.json());
}
