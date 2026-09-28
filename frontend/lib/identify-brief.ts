import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const identifyBriefThemeSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  summary: z.string().min(1),
  evidenceCount: z.number().int().nonnegative(),
  evidenceIds: z.array(z.string().uuid()),
  isLead: z.boolean()
});

const identifyBriefEvidenceSchema = z.object({
  id: z.string().uuid(),
  sourceActivity: z.string().min(1).nullable(),
  sourceLabel: z.string().min(1),
  claim: z.string().min(1),
  summary: z.string().min(1).nullable(),
  coverageAreaIds: z.array(z.string().min(1)),
  evidenceStatus: z.enum(["user-confirmed", "source-derived", "ai-inferred"]),
  sourceReference: z.string().min(1).nullable(),
  derivedFromEvidenceIds: z.array(z.string().uuid())
});

const identifyBriefQuestionSchema = z.object({
  id: z.string().min(1),
  question: z.string().min(1),
  source: z.string().min(1),
  supportingEvidenceIds: z.array(z.string().uuid())
});

const identifyBriefCoverageSchema = z.object({
  areaId: z.string().min(1),
  label: z.string().min(1),
  question: z.string().min(1),
  status: z.enum(["uncovered", "partial", "sufficient"]),
  evidenceCount: z.number().int().nonnegative()
});

const identifyBriefReadinessSchema = z.object({
  isReady: z.boolean(),
  coveredAreaCount: z.number().int().nonnegative(),
  totalAreaCount: z.number().int().positive(),
  requiredEvidenceSources: z.array(z.string().min(1)),
  missing: z.array(z.string().min(1))
});

const identifyBriefResponseSchema = z.object({
  activity_id: z.literal("identify-brief"),
  organisationName: z.string().min(1),
  website: z.string().min(1).nullable(),
  statement: z.string().min(1),
  evidenceCount: z.number().int().nonnegative(),
  sourceBreakdown: z.object({
    discover: z.number().int().nonnegative(),
    listen: z.number().int().nonnegative(),
    understand: z.number().int().nonnegative()
  }),
  themes: z.array(identifyBriefThemeSchema),
  strongestEvidence: z.array(identifyBriefEvidenceSchema),
  openQuestions: z.array(identifyBriefQuestionSchema),
  coverage: z.array(identifyBriefCoverageSchema),
  unresolvedGapCount: z.number().int().nonnegative(),
  readiness: identifyBriefReadinessSchema,
  handoffLabel: z.string().min(1)
});

const identifyCompletionIssueSchema = z.object({
  code: z.string().min(1),
  message: z.string().min(1),
  activityId: z.string().min(1).nullable(),
  evidenceIds: z.array(z.string().uuid())
});

const identifyCompletionReadinessSchema = z.object({
  status: z.enum(["in-progress", "ready-for-review", "completed"]),
  canComplete: z.boolean(),
  blockingIssues: z.array(identifyCompletionIssueSchema),
  openQuestions: z.array(z.string().min(1))
});

const handoffCoverageSchema = z.object({
  areaId: z.string().min(1),
  label: z.string().min(1),
  question: z.string().min(1),
  status: z.enum(["uncovered", "partial", "sufficient"]),
  evidenceIds: z.array(z.string().uuid()),
  updatedAt: z.string().datetime()
});

const identifyHandoffSchema = z.object({
  assessmentId: z.string().uuid(),
  fromStage: z.literal("identify"),
  toStage: z.literal("define"),
  completionStatus: z.literal("completed"),
  completedAt: z.string().datetime(),
  output: z.record(z.string(), z.unknown()),
  brief: identifyBriefResponseSchema,
  coverage: z.array(handoffCoverageSchema),
  strongestEvidenceIds: z.array(z.string().uuid()),
  evidenceReferences: z.array(z.string().uuid()),
  openQuestions: z.array(z.string().min(1)),
  revisitHistory: z.array(
    z.object({
      topic: z.string().min(1),
      reason: z.string().min(1),
      created_at: z.string().datetime()
    })
  )
});

const identifyCompletionResponseSchema = z.object({
  readiness: identifyCompletionReadinessSchema,
  handoff: identifyHandoffSchema.nullable()
});

export type IdentifyBriefTheme = z.infer<typeof identifyBriefThemeSchema>;
export type IdentifyBriefEvidence = z.infer<typeof identifyBriefEvidenceSchema>;
export type IdentifyBriefResponse = z.infer<typeof identifyBriefResponseSchema>;
export type IdentifyCompletionResponse = z.infer<
  typeof identifyCompletionResponseSchema
>;

export async function getIdentifyBrief(
  sessionId: string
): Promise<IdentifyBriefResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/brief`
  );

  if (!response.ok) {
    throw new Error("Unable to load Identify Brief.");
  }

  return identifyBriefResponseSchema.parse(await response.json());
}

export async function getIdentifyCompletion(
  sessionId: string
): Promise<IdentifyCompletionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/completion`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error("Unable to load Identify completion status.");
  }
  return identifyCompletionResponseSchema.parse(await response.json());
}

export async function completeIdentify(
  sessionId: string
): Promise<IdentifyCompletionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/complete`,
    { method: "POST" }
  );
  const payload: unknown = await response.json();
  if (response.status === 409) {
    const errorPayload = z.object({ detail: identifyCompletionReadinessSchema }).parse(payload);
    return { readiness: errorPayload.detail, handoff: null };
  }
  if (!response.ok) {
    throw new Error("Unable to complete Identify.");
  }
  return identifyCompletionResponseSchema.parse(payload);
}
