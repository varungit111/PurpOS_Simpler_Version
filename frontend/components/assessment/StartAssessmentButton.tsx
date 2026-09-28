"use client";

import {
  assessmentResumePath,
  getAssessmentSession,
  type AssessmentSession
} from "@/lib/sessions";
import {
  getRememberedAssessment,
  validateRememberedAssessment
} from "@/lib/assessment-pointer";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function StartAssessmentButton() {
  const router = useRouter();
  const [resumeSession, setResumeSession] = useState<AssessmentSession | null>(
    null
  );
  const [isResuming, setIsResuming] = useState(false);

  useEffect(() => {
    let isCurrent = true;
    const rememberedId = getRememberedAssessment();

    if (!rememberedId) return;

    validateRememberedAssessment({
      assessmentId: rememberedId,
      loadSession: getAssessmentSession,
      resumePath: assessmentResumePath
    })
      .then((session) => {
        if (isCurrent) setResumeSession(session);
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  function handleStart() {
    router.push("/identify/who-are-you");
  }

  function handleResume() {
    if (!resumeSession || isResuming) return;
    const resumePath = assessmentResumePath(resumeSession);
    if (!resumePath) return;

    setIsResuming(true);
    router.push(resumePath);
  }

  return (
    <div className="flex flex-col items-stretch gap-3 sm:items-end">
      <button
        className="inline-flex min-h-11 items-center justify-center rounded-lg bg-purpos-violet px-5 text-sm font-semibold text-white shadow-sm outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
        onClick={handleStart}
        type="button"
      >
        Take the leap
        <span aria-hidden="true" className="ml-2">
          -&gt;
        </span>
      </button>
      {resumeSession ? (
        <button
          className="min-h-10 px-2 text-sm font-semibold text-purpos-violet underline decoration-1 underline-offset-4 outline-none hover:text-[#6043a2] focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
          disabled={isResuming}
          onClick={handleResume}
          type="button"
        >
          {isResuming ? "Continuing..." : "Continue assessment"}
        </button>
      ) : null}
    </div>
  );
}
