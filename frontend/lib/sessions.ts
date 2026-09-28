import { z } from "zod";
import { isConfirmedUnusableAssessmentStatus } from "./assessment-pointer";
export { assessmentResumePath } from "./assessment-resume-path";
import { API_BASE_URL } from "./api-config";

const assessmentSessionSchema = z.object({
  id: z.string().uuid(),
  stage: z.enum([
    "identify",
    "define",
    "stress_test",
    "align",
    "results",
    "measure"
  ]),
  lifecycle_status: z.enum(["created", "active", "stage_completed"]),
  next_stage: z.enum([
    "identify",
    "define",
    "stress_test",
    "align",
    "results",
    "measure"
  ]).nullable(),
  stage_statuses: z.partialRecord(
    z.enum(["identify", "define", "stress_test", "align", "results", "measure"]),
    z.enum(["not_started", "in_progress", "completed"])
  ),
  organisation: z.object({
    companyName: z.string().min(1).nullable()
  }),
  version: z.number().int().positive()
});

export type AssessmentSession = z.infer<typeof assessmentSessionSchema>;

export async function createAssessmentSession(
  payload: {
    companyName?: string;
    website?: string;
  } = {}
): Promise<AssessmentSession> {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error("Unable to start assessment.");
  }

  return assessmentSessionSchema.parse(await response.json());
}

export async function getAssessmentSession(
  assessmentId: string
): Promise<AssessmentSession | null> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${assessmentId}`, {
    cache: "no-store"
  });

  if (isConfirmedUnusableAssessmentStatus(response.status)) {
    return null;
  }
  if (!response.ok) {
    throw new Error("Unable to resume assessment.");
  }
  return assessmentSessionSchema.parse(await response.json());
}
