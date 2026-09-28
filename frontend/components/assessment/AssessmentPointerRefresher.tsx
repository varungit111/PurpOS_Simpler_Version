"use client";

import { validateRememberedAssessment } from "@/lib/assessment-pointer";
import {
  assessmentResumePath,
  getAssessmentSession,
  type AssessmentSession
} from "@/lib/sessions";
import { useEffect, useState, type ReactNode } from "react";
import { AssessmentSessionContext } from "./AssessmentSessionContext";

export function AssessmentPointerRefresher({
  assessmentId,
  children
}: {
  assessmentId: string;
  children: ReactNode;
}) {
  const [session, setSession] = useState<AssessmentSession | null>(null);

  useEffect(() => {
    let isCurrent = true;

    validateRememberedAssessment({
      assessmentId,
      loadSession: getAssessmentSession,
      resumePath: assessmentResumePath
    }).then((validatedSession) => {
      if (isCurrent) setSession(validatedSession);
    });

    return () => {
      isCurrent = false;
    };
  }, [assessmentId]);

  return (
    <AssessmentSessionContext.Provider value={session}>
      {children}
    </AssessmentSessionContext.Provider>
  );
}
