import { z } from "zod";
import { API_BASE_URL } from "./api-config";

const provenance = z.object({ status: z.enum(["user-confirmed", "source-derived", "ai-inferred"]), rationale: z.string().nullable(), generatedAt: z.string().datetime().nullable(), updatedAt: z.string().datetime().nullable(), sourceHandoff: z.string().nullable() });
const criterion = z.object({ criterionId: z.string(), name: z.string(), question: z.string(), status: z.enum(["supported", "needs-review", "insufficient-evidence"]), reasoning: z.string(), supportingEvidenceIds: z.array(z.string().uuid()), concerns: z.array(z.string()), suggestedRefinement: z.string().nullable(), provenance, approvalStatus: z.enum(["ai-proposed", "user-edited", "agreed"]) });
const state = z.object({ assessmentId: z.string().uuid().nullable(), status: z.enum(["not_started", "in_progress", "ready_for_review", "completed"]), criteria: z.array(criterion), overarchingQuestion: z.string(), overarchingResponse: z.string().nullable(), evidenceReferences: z.array(z.string().uuid()), provenance, version: z.number(), createdAt: z.string(), updatedAt: z.string() }).passthrough();
const responseSchema = z.object({ stressTest: state });
export type StressTestState = z.infer<typeof state>;
export type StressTestCriterion = z.infer<typeof criterion>;

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Unable to update the Stress Test.");
  }
  return responseSchema.parse(await response.json()).stressTest;
}
export const getStressTest = (id: string) => request(`/api/sessions/${id}/stress-test`, { cache: "no-store" });
export const evaluateStressTest = (id: string) => request(`/api/sessions/${id}/stress-test/evaluate`, { method: "POST" });
export const updateStressTestReview = (id: string, overarchingResponse: string) => request(`/api/sessions/${id}/stress-test/review`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ overarchingResponse }) });
export const completeStressTest = (id: string) => request(`/api/sessions/${id}/stress-test/complete`, { method: "POST" });
export async function updateStressTestCriterion(id: string, criterionId: string, payload: Partial<Pick<StressTestCriterion, "status" | "reasoning" | "concerns" | "suggestedRefinement" | "approvalStatus">>) {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${id}/stress-test/criteria/${criterionId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(typeof body?.detail === "string" ? body.detail : "Unable to save criterion review."); }
  return z.object({ criterion }).parse(await response.json()).criterion;
}
