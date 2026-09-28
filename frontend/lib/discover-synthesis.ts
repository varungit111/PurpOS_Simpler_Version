import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const discoverSynthesisProgressSchema = z.object({
  evidenceCount: z.number().int().nonnegative(),
  label: z.string().min(1)
});

const discoverSynthesisResponseSchema = z.object({
  activity_id: z.literal("discover-synthesis"),
  statement: z.string().min(1).nullable(),
  gauge_items: z.array(z.string().min(1)),
  progress: discoverSynthesisProgressSchema,
  message: z.string().min(1).nullable()
});

export type DiscoverSynthesisProgress = z.infer<
  typeof discoverSynthesisProgressSchema
>;
export type DiscoverSynthesisResponse = z.infer<
  typeof discoverSynthesisResponseSchema
>;

export async function getDiscoverSynthesis(
  sessionId: string
): Promise<DiscoverSynthesisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/discover-synthesis`
  );

  if (!response.ok) {
    throw new Error("Unable to load Discover Synthesis.");
  }

  return discoverSynthesisResponseSchema.parse(await response.json());
}

export async function generateDiscoverSynthesis(
  sessionId: string
): Promise<DiscoverSynthesisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/discover-synthesis/generate`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    throw new Error("Unable to generate Discover Synthesis.");
  }

  return discoverSynthesisResponseSchema.parse(await response.json());
}

export async function saveDiscoverSynthesis({
  sessionId,
  statement
}: {
  sessionId: string;
  statement: string;
}): Promise<DiscoverSynthesisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/discover-synthesis`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ statement })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save Discover Synthesis.");
  }

  return discoverSynthesisResponseSchema.parse(await response.json());
}
