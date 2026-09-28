import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const approvalStatusSchema = z.enum(["ai-proposed", "user-edited", "agreed"]);
const evidenceStatusSchema = z.enum([
  "user-confirmed",
  "source-derived",
  "ai-inferred"
]);
const momentStatusSchema = z.enum([
  "on-course",
  "in-progress",
  "gap-to-close"
]);

const defineProvenanceSchema = z.object({
  status: evidenceStatusSchema,
  rationale: z.string().min(1).nullable(),
  generatedAt: z.string().datetime().nullable(),
  updatedAt: z.string().datetime().nullable(),
  sourceHandoff: z.string().min(1).nullable()
});

const soiCandidateSchema = z.object({
  id: z.string().uuid(),
  statement: z.string().min(1).nullable(),
  guidingStar: z.string().min(1).nullable(),
  meaning: z.string().min(1).nullable(),
  evidenceIds: z.array(z.string().uuid()),
  provenance: defineProvenanceSchema,
  approvalStatus: approvalStatusSchema
});

const positioningStatementSchema = z.object({
  audience: z.string().min(1).nullable(),
  categoryContext: z.string().min(1).nullable(),
  capabilityValue: z.string().min(1).nullable(),
  reasonBelievability: z.string().min(1).nullable(),
  composedStatement: z.string().min(1).nullable(),
  evidenceIds: z.array(z.string().uuid()),
  provenance: defineProvenanceSchema,
  approvalStatus: approvalStatusSchema
});

const valueCommitmentSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  meaning: z.string().min(1).nullable(),
  supportingEvidence: z.array(z.string().min(1)),
  evidenceIds: z.array(z.string().uuid()),
  provenance: defineProvenanceSchema,
  approvalStatus: approvalStatusSchema
});

const valueChainMomentSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  question: z.string().min(1).nullable(),
  today: z.string().min(1).nullable(),
  desiredState: z.string().min(1).nullable(),
  theMove: z.string().min(1).nullable(),
  status: momentStatusSchema,
  supportingEvidence: z.array(z.string().min(1)),
  evidenceIds: z.array(z.string().uuid()),
  provenance: defineProvenanceSchema,
  approvalStatus: approvalStatusSchema
});

const defineOutputSchema = z.object({
  agreedSoi: soiCandidateSchema.nullable(),
  agreedPositioning: positioningStatementSchema.nullable(),
  agreedValues: z.array(valueCommitmentSchema),
  agreedMoments: z.array(valueChainMomentSchema),
  unresolvedQuestions: z.array(z.string().min(1)),
  evidenceReferences: z.array(z.string().uuid()),
  sourceHandoff: z.string().min(1).nullable()
});

export const defineStateSchema = z.object({
  assessmentId: z.string().uuid().nullable(),
  status: z.enum([
    "not_started",
    "in_progress",
    "ready_for_review",
    "completed"
  ]),
  sourceHandoff: z.string().min(1).nullable(),
  soiCandidate: soiCandidateSchema.nullable(),
  positioning: positioningStatementSchema,
  values: z.array(valueCommitmentSchema),
  moments: z.array(valueChainMomentSchema),
  unresolvedQuestions: z.array(z.string().min(1)),
  evidenceReferences: z.array(z.string().uuid()),
  provenance: defineProvenanceSchema,
  output: defineOutputSchema.nullable(),
  version: z.number().int().positive(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

const defineStateResponseSchema = z.object({ define: defineStateSchema });

async function apiError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = z.object({ detail: z.string() }).parse(await response.json());
    return new Error(payload.detail);
  } catch {
    return new Error(fallback);
  }
}

export type DefineState = z.infer<typeof defineStateSchema>;
export type PositioningStatement = z.infer<typeof positioningStatementSchema>;
export type ValueCommitment = z.infer<typeof valueCommitmentSchema>;
export type ValueChainMoment = z.infer<typeof valueChainMomentSchema>;
export type ValueChainMomentStatus = ValueChainMoment["status"];

export const momentStatusOptions: ReadonlyArray<{
  value: ValueChainMomentStatus;
  label: string;
}> = [
  { value: "on-course", label: "On Course" },
  { value: "in-progress", label: "In Progress" },
  { value: "gap-to-close", label: "A Gap to Close" }
];
export type PositioningStatementPatch = Partial<
  Pick<
    PositioningStatement,
    | "audience"
    | "categoryContext"
    | "capabilityValue"
    | "reasonBelievability"
    | "composedStatement"
    | "evidenceIds"
    | "approvalStatus"
  >
>;
export type ValueCommitmentPatch = Partial<
  Pick<
    ValueCommitment,
    "name" | "meaning" | "supportingEvidence" | "evidenceIds" | "approvalStatus"
  >
>;
export type ValueChainMomentPatch = Partial<
  Pick<
    ValueChainMoment,
    | "name"
    | "question"
    | "today"
    | "desiredState"
    | "theMove"
    | "status"
    | "supportingEvidence"
    | "evidenceIds"
    | "approvalStatus"
  >
>;

export async function getDefine(sessionId: string): Promise<DefineState> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/define`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to load Define state.");
  }

  return defineStateResponseSchema.parse(await response.json()).define;
}

export async function generateDefine(sessionId: string): Promise<DefineState> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/define/generate`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw await apiError(response, "Unable to generate Define proposal.");
  }

  return defineStateResponseSchema.parse(await response.json()).define;
}

export async function agreeDefineSoi(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/define/soi`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approvalStatus: "agreed" })
  });
  if (!response.ok) throw await apiError(response, "Unable to agree the SOI.");
  return z.object({ soi: soiCandidateSchema }).parse(await response.json()).soi;
}

const defineReadinessSchema = z.object({
  status: z.enum(["not_started", "in_progress", "ready_for_review", "completed"]),
  canComplete: z.boolean(),
  blockingIssues: z.array(z.object({ code: z.string(), message: z.string(), evidenceIds: z.array(z.string().uuid()) })),
  openQuestions: z.array(z.string())
});
export type DefineReadiness = z.infer<typeof defineReadinessSchema>;

export async function getDefineCompletion(sessionId: string): Promise<DefineReadiness> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/define/completion`, { cache: "no-store" });
  if (!response.ok) throw await apiError(response, "Unable to check Define readiness.");
  return z.object({ readiness: defineReadinessSchema }).parse(await response.json()).readiness;
}

export async function completeDefine(sessionId: string): Promise<DefineReadiness> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/define/complete`, { method: "POST" });
  if (!response.ok) throw await apiError(response, "Define is not ready to complete.");
  return z.object({ readiness: defineReadinessSchema }).parse(await response.json()).readiness;
}

export async function updateDefinePositioning(
  sessionId: string,
  payload: PositioningStatementPatch
): Promise<PositioningStatement> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/define/positioning`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );

  if (!response.ok) {
    throw await apiError(response, "Unable to update Define positioning.");
  }

  return z
    .object({ positioning: positioningStatementSchema })
    .parse(await response.json()).positioning;
}

export async function updateDefineValue(
  sessionId: string,
  valueId: string,
  payload: ValueCommitmentPatch
): Promise<ValueCommitment> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/define/values/${valueId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );

  if (!response.ok) {
    throw await apiError(response, "Unable to update Define value.");
  }

  return z.object({ value: valueCommitmentSchema }).parse(await response.json()).value;
}

export async function updateDefineMoment(
  sessionId: string,
  momentId: string,
  payload: ValueChainMomentPatch
): Promise<ValueChainMoment> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/define/moments/${momentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );

  if (!response.ok) {
    throw await apiError(response, "Unable to update Define moment.");
  }

  return z
    .object({ moment: valueChainMomentSchema })
    .parse(await response.json()).moment;
}
