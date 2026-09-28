export type ReviewModeSession = {
  stage: "identify" | "define" | "stress_test" | "align" | "results" | "measure";
  stage_statuses: Partial<
    Record<
      "identify" | "define" | "stress_test" | "align" | "results" | "measure",
      "not_started" | "in_progress" | "completed"
    >
  >;
};

const stageOrder = [
  "identify",
  "define",
  "stress_test",
  "align",
  "results",
  "measure"
] as const;

export function isStageReviewOnly(
  session: ReviewModeSession | null,
  stage: "identify" | "define"
): boolean {
  if (!session || session.stage_statuses[stage] !== "completed") return false;
  return stageOrder.indexOf(session.stage) > stageOrder.indexOf(stage);
}
