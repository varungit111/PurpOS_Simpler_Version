import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const provenance = z.object({
  status: z.enum(["user-confirmed", "source-derived", "ai-inferred"]),
  rationale: z.string().nullable(),
  generatedAt: z.string().datetime().nullable(),
  updatedAt: z.string().datetime().nullable(),
  sourceHandoff: z.string().nullable()
});

const suggestedMove = z.object({
  id: z.string().uuid(),
  action: z.string(),
  rationale: z.string(),
  relatedGapId: z.string().uuid().nullable(),
  relatedGateId: z.string().nullable(),
  relatedDecisionId: z.string().uuid(),
  evidenceReferences: z.array(z.string().uuid()),
  status: z.enum(["proposed", "adopted", "in-progress", "completed", "dismissed"]),
  adopted: z.boolean(),
  provenance
});

const valueGate = z.object({
  gateId: z.string(),
  frameworkReference: z.string(),
  frameworkLabel: z.string(),
  status: z.enum(["aligned", "tension", "gap", "insufficient-evidence"]),
  reasoning: z.string(),
  supportingEvidenceIds: z.array(z.string().uuid()),
  tensions: z.array(z.string()),
  provenance
});

const decision = z.object({
  id: z.string().uuid(),
  originalQuestion: z.string(),
  reframedQuestion: z.string().nullable(),
  reframeReasoning: z.string().nullable(),
  valueGates: z.array(valueGate),
  gapIds: z.array(z.string().uuid()),
  suggestedMoves: z.array(suggestedMove),
  adoptedActionIds: z.array(z.string().uuid()),
  evidenceReferences: z.array(z.string().uuid()),
  status: z.enum(["draft", "reframed", "evaluated"]),
  provenance,
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});

const progressSnapshot = z.object({
  id: z.string().uuid(),
  capturedAt: z.string().datetime(),
  completedActionIds: z.array(z.string().uuid()),
  outstandingActionIds: z.array(z.string().uuid()),
  adoptedActionIds: z.array(z.string().uuid()),
  resolvedGapIds: z.array(z.string().uuid()),
  unresolvedGapIds: z.array(z.string().uuid()),
  observations: z.array(z.string()),
  evidenceReferences: z.array(z.string().uuid())
});

const alignmentGap = z.object({
  id: z.string().uuid(),
  title: z.string(),
  description: z.string(),
  relatedFunctionId: z.string().uuid().nullable(),
  relatedFrameworkRefs: z.array(z.string()),
  supportingEvidenceIds: z.array(z.string().uuid()),
  conflictingEvidenceIds: z.array(z.string().uuid()),
  whyItMatters: z.string(),
  suggestedNextAction: z.string().nullable(),
  status: z.enum(["proposed", "adopted", "in-progress", "completed", "dismissed"]),
  provenance
});

const priorityAction = z.object({
  id: z.string().uuid(),
  title: z.string(),
  action: z.string(),
  rationale: z.string(),
  relatedGapId: z.string().uuid().nullable(),
  relatedFunctionId: z.string().uuid().nullable(),
  evidenceReferences: z.array(z.string().uuid()),
  status: z.enum(["proposed", "adopted", "in-progress", "completed", "dismissed"]),
  adopted: z.boolean(),
  order: z.number().int().nonnegative(),
  provenance
});

const adoptedAction = z.object({
  id: z.string().uuid(),
  sourceMoveId: z.string().uuid(),
  decisionId: z.string().uuid(),
  action: z.string(),
  rationale: z.string(),
  evidenceReferences: z.array(z.string().uuid()),
  status: z.enum(["proposed", "adopted", "in-progress", "completed", "dismissed"]),
  adoptedAt: z.string().datetime(),
  provenance
});

const alignmentState = z.object({
  assessmentId: z.string().uuid().nullable(),
  status: z.enum(["not_started", "in_progress"]),
  functionalAlignment: z.array(z.object({
    id: z.string().uuid(),
    functionName: z.string(),
    status: z.enum(["aligned", "tension", "gap", "insufficient-evidence"]),
    reasoning: z.string(),
    evidenceReferences: z.array(z.string().uuid()),
    gapIds: z.array(z.string().uuid()),
    actionIds: z.array(z.string().uuid()),
    provenance
  })),
  gaps: z.array(alignmentGap),
  priorityActions: z.array(priorityAction),
  decisions: z.array(decision),
  adoptedActions: z.array(adoptedAction),
  progressSnapshots: z.array(progressSnapshot),
  unresolvedQuestions: z.array(z.string()),
  evidenceReferences: z.array(z.string().uuid()),
  version: z.number().int().positive(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
}).passthrough();

export type AlignmentState = z.infer<typeof alignmentState>;
export type DecisionCanvas = z.infer<typeof decision>;
export type SuggestedMove = z.infer<typeof suggestedMove>;
export type ProgressSnapshot = z.infer<typeof progressSnapshot>;
export type AlignmentGap = z.infer<typeof alignmentGap>;
export type PriorityAction = z.infer<typeof priorityAction>;
export type AdoptedAction = z.infer<typeof adoptedAction>;

const alignmentContext = z.object({
  organisation: z.object({ companyName: z.string().nullable() }).passthrough(),
  define: z.object({
    output: z.object({
      agreedSoi: z.object({ statement: z.string().nullable() }).nullable(),
      agreedPositioning: z.object({ composedStatement: z.string().nullable() }).nullable(),
      agreedValues: z.array(z.object({ id: z.string().uuid(), name: z.string() }))
    }).nullable()
  }).passthrough(),
  stress_test: z.object({
    output: z.object({ overarchingResponse: z.string().nullable() }).nullable()
  }).passthrough()
});
export type AlignmentContext = z.infer<typeof alignmentContext>;

async function api(path: string, schema: z.ZodType, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Unable to update Alignment.");
  }
  return schema.parse(await response.json());
}

const jsonHeaders = { "Content-Type": "application/json" };
export async function getAlignment(id: string) {
  return (await api(`/api/sessions/${id}/align`, z.object({ alignment: alignmentState }), { cache: "no-store" }) as { alignment: AlignmentState }).alignment;
}
export async function generateAlignment(id: string) {
  return (await api(`/api/sessions/${id}/align/generate`, z.object({ alignment: alignmentState }), { method: "POST" }) as { alignment: AlignmentState }).alignment;
}
export async function createDecision(id: string, question: string) {
  return (await api(`/api/sessions/${id}/align/decisions`, z.object({ decision }), { method: "POST", headers: jsonHeaders, body: JSON.stringify({ question }) }) as { decision: DecisionCanvas }).decision;
}
export async function reframeDecision(id: string, decisionId: string) {
  return (await api(`/api/sessions/${id}/align/decisions/${decisionId}/reframe`, z.object({ decision }), { method: "POST" }) as { decision: DecisionCanvas }).decision;
}
export async function evaluateDecision(id: string, decisionId: string) {
  return (await api(`/api/sessions/${id}/align/decisions/${decisionId}/evaluate`, z.object({ decision }), { method: "POST" }) as { decision: DecisionCanvas }).decision;
}
export async function setMoveAdoption(id: string, moveId: string, adopted: boolean) {
  return (await api(`/api/sessions/${id}/align/moves/${moveId}`, z.object({ move: suggestedMove }), { method: "PATCH", headers: jsonHeaders, body: JSON.stringify({ adopted }) }) as { move: SuggestedMove }).move;
}
export async function getAlignmentProgress(id: string) {
  return (await api(`/api/sessions/${id}/align/progress`, z.object({ snapshots: z.array(progressSnapshot) }), { cache: "no-store" }) as { snapshots: ProgressSnapshot[] }).snapshots;
}

export async function getAlignmentContext(id: string): Promise<AlignmentContext> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(response.status === 404 ? "Assessment not found." : "Unable to load purpose context.");
  return alignmentContext.parse(await response.json());
}
