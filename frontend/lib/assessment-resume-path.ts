export type ResumableAssessmentSession = {
  id: string;
  stage: "identify" | "define" | "stress_test" | "align" | "results" | "measure";
  stage_statuses: Partial<
    Record<
      "identify" | "define" | "stress_test" | "align" | "results" | "measure",
      "not_started" | "in_progress" | "completed"
    >
  >;
};

export function assessmentResumePath(
  session: ResumableAssessmentSession
): string | null {
  if (session.stage === "identify") {
    if (session.stage_statuses.identify === "completed") {
      return `/assessments/${session.id}/identify/brief`;
    }
    return `/assessments/${session.id}/identify`;
  }
  if (session.stage === "define") {
    return `/assessments/${session.id}/define`;
  }
  if (session.stage === "stress_test") {
    return `/assessments/${session.id}/stress-test`;
  }
  if (session.stage === "align") {
    return `/assessments/${session.id}/align`;
  }
  return null;
}
