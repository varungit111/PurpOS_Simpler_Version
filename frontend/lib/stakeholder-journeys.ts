import { stakeholderSchema } from "./stakeholders";
import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const journeyNoteSchema = z.object({
  id: z.string().uuid(),
  summary: z.string().min(1)
});

const observedExperienceSchema = z.object({
  id: z.string().uuid(),
  summary: z.string().min(1),
  supportingEvidence: z.array(z.string().min(1))
});

export const touchpointSchema = z.object({
  id: z.string().uuid(),
  moment: z.string().min(1),
  expectations: z.array(journeyNoteSchema),
  observedExperiences: z.array(observedExperienceSchema),
  painPoints: z.array(z.string().min(1)),
  gaps: z.array(journeyNoteSchema),
  opportunities: z.array(journeyNoteSchema),
  supportingEvidence: z.array(z.string().min(1))
});

export const stakeholderJourneySchema = z.object({
  id: z.string().uuid(),
  stakeholderId: z.string().uuid(),
  stakeholderName: z.string().min(1),
  touchpoints: z.array(touchpointSchema),
  supportingEvidence: z.array(z.string().min(1)),
  sourceActivity: z.literal("day-in-their-shoes"),
  sourceLabel: z.string().min(1),
  collectedAt: z.string().min(1)
});

const stakeholderJourneyProgressSchema = z.object({
  journeyCount: z.number().int().nonnegative(),
  stakeholderCount: z.number().int().nonnegative(),
  label: z.string().min(1)
});

const stakeholderJourneyResponseSchema = z.object({
  activity_id: z.literal("day-in-their-shoes"),
  activity_status: z.enum(["locked", "available"]),
  dependency_message: z.string().min(1).nullable(),
  progress: stakeholderJourneyProgressSchema,
  stakeholders: z.array(stakeholderSchema),
  journeys: z.array(stakeholderJourneySchema),
  message: z.string().min(1).nullable()
});

export type Touchpoint = z.infer<typeof touchpointSchema>;
export type StakeholderJourney = z.infer<typeof stakeholderJourneySchema>;
export type StakeholderJourneyResponse = z.infer<
  typeof stakeholderJourneyResponseSchema
>;

export async function getStakeholderJourneys(
  sessionId: string
): Promise<StakeholderJourneyResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/stakeholder-journeys`
  );

  if (!response.ok) {
    throw new Error("Unable to load stakeholder journeys.");
  }

  return stakeholderJourneyResponseSchema.parse(await response.json());
}

export async function saveStakeholderJourneys({
  sessionId,
  journeys
}: {
  sessionId: string;
  journeys: StakeholderJourney[];
}): Promise<StakeholderJourneyResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/stakeholder-journeys`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ journeys })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save stakeholder journeys.");
  }

  return stakeholderJourneyResponseSchema.parse(await response.json());
}
