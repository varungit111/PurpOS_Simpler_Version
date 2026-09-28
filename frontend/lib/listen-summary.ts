import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const listenSummaryAreaSchema = z.object({
  areaId: z.string().min(1),
  label: z.string().min(1),
  status: z.string().min(1),
  evidenceCount: z.number().int().nonnegative(),
  note: z.string().min(1)
});

const listenSummaryQuoteSchema = z.object({
  id: z.string().min(1),
  sourceActivity: z.string().min(1),
  text: z.string().min(1)
});

const listenSummaryResponseSchema = z.object({
  activity_id: z.literal("listen-summary"),
  evidenceCount: z.number().int().nonnegative(),
  stakeholderCount: z.number().int().nonnegative(),
  hotSeatEvidenceCount: z.number().int().nonnegative(),
  companyCardsCount: z.number().int().nonnegative(),
  areasMoved: z.array(listenSummaryAreaSchema),
  quotes: z.array(listenSummaryQuoteSchema),
  tension: z.string().min(1).nullable(),
  message: z.string().min(1).nullable()
});

export type ListenSummaryResponse = z.infer<typeof listenSummaryResponseSchema>;

export async function getListenSummary(
  sessionId: string
): Promise<ListenSummaryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/listen-summary`
  );

  if (!response.ok) {
    throw new Error("Unable to load Listen Summary.");
  }

  return listenSummaryResponseSchema.parse(await response.json());
}
