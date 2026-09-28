import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const organisationSchema = z.object({
  companyName: z.string().min(1).nullable(),
  website: z.string().url().nullable()
});

const identifyActivityStateSchema = z.object({
  activityId: z.string().min(1),
  status: z.enum([
    "available",
    "ai-running",
    "needs-user",
    "invite-team",
    "completed",
    "locked",
    "conditional",
    "ready-for-review"
  ]),
  progressLabel: z.string().min(1).nullable(),
  updatedAt: z.string().min(1)
});

const playbookCoverageSchema = z.object({
  areaId: z.string().min(1),
  label: z.string().min(1),
  question: z.string().min(1),
  status: z.enum(["uncovered", "partial", "sufficient"]),
  evidenceIds: z.array(z.string().uuid()),
  updatedAt: z.string().min(1)
});

const identifyBoardStateSchema = z.object({
  activity_id: z.literal("investigation-board"),
  organisation: organisationSchema,
  activities: z.array(identifyActivityStateSchema),
  playbookCoverage: z.array(playbookCoverageSchema),
  confidence: z.object({
    overall: z.number().int().min(0).max(100),
    sufficientAreas: z.number().int().nonnegative(),
    partialAreas: z.number().int().nonnegative(),
    totalAreas: z.number().int().positive()
  })
});

export type IdentifyBoardState = z.infer<typeof identifyBoardStateSchema>;
export type IdentifyActivityState = z.infer<typeof identifyActivityStateSchema>;
export type PlaybookCoverage = z.infer<typeof playbookCoverageSchema>;

export async function getIdentifyBoardState(
  sessionId: string
): Promise<IdentifyBoardState> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/board`
  );

  if (!response.ok) {
    throw new Error("Unable to load Identify board state.");
  }

  return identifyBoardStateSchema.parse(await response.json());
}
