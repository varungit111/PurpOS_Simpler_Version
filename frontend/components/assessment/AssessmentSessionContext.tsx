"use client";

import type { AssessmentSession } from "@/lib/sessions";
import { isStageReviewOnly } from "@/lib/assessment-review-mode";
import { createContext, useContext } from "react";

export const AssessmentSessionContext =
  createContext<AssessmentSession | null>(null);

export function useAssessmentSession() {
  return useContext(AssessmentSessionContext);
}

export function useStageReviewMode(stage: "identify" | "define") {
  const session = useAssessmentSession();
  return isStageReviewOnly(session, stage);
}
