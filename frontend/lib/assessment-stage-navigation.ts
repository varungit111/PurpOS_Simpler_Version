export type AssessmentStageNavigationSession = {
  id: string;
  stage: "identify" | "define" | "stress_test" | "align" | "results" | "measure";
  stage_statuses: Partial<
    Record<
      "identify" | "define" | "stress_test" | "align" | "results" | "measure",
      "not_started" | "in_progress" | "completed"
    >
  >;
};

export type AssessmentStageNavigationItem = {
  id: "identify" | "define" | "stress_test" | "align" | "measure";
  label: string;
  position: string;
  state: "completed" | "current" | "disabled";
  href: string | null;
};

const stageDefinitions = [
  { id: "identify", label: "Identify", position: "01" },
  { id: "define", label: "Define", position: "02" },
  { id: "stress_test", label: "Stress Test", position: "03" },
  { id: "align", label: "Align", position: "04" },
  { id: "measure", label: "Measure", position: "05" }
] as const;

export function buildAssessmentStageNavigation(
  session: AssessmentStageNavigationSession | null
): AssessmentStageNavigationItem[] {
  return stageDefinitions.map((stage) => {
    const isCurrent = session?.stage === stage.id;
    const isCompleted = session?.stage_statuses[stage.id] === "completed";
    const state = isCurrent
      ? "current"
      : isCompleted
        ? "completed"
        : "disabled";
    const route = session ? stageRoute(stage.id, session.id) : null;

    return {
      ...stage,
      state,
      href: state !== "disabled" ? route : null
    };
  });
}

function stageRoute(
  stage: AssessmentStageNavigationItem["id"],
  assessmentId: string
): string | null {
  if (stage === "identify") {
    return `/assessments/${assessmentId}/identify`;
  }
  if (stage === "define") {
    return `/assessments/${assessmentId}/define/review`;
  }
  if (stage === "stress_test") {
    return `/assessments/${assessmentId}/stress-test`;
  }
  if (stage === "align") {
    return `/assessments/${assessmentId}/align`;
  }
  return null;
}
