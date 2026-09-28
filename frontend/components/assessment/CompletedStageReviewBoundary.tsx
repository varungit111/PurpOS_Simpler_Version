"use client";

import { useStageReviewMode } from "./AssessmentSessionContext";
import type { FormEvent, KeyboardEvent, MouseEvent, ReactNode } from "react";

export function CompletedStageReviewBoundary({
  children,
  stage
}: {
  children: ReactNode;
  stage: "identify" | "define";
}) {
  const reviewOnly = useStageReviewMode(stage);

  function blockMutationClick(event: MouseEvent<HTMLDivElement>) {
    if (!reviewOnly) return;
    const target = event.target as HTMLElement;
    if (
      target.closest("[data-stage-mutation]") ||
      target.matches("input, textarea, select")
    ) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function blockFormSubmit(event: FormEvent<HTMLDivElement>) {
    if (!reviewOnly) return;
    event.preventDefault();
    event.stopPropagation();
  }

  function blockFormKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (!reviewOnly) return;
    const target = event.target as HTMLElement;
    if (target.matches("input, textarea, select")) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  return (
    <div
      className={
        reviewOnly
          ? "[&_input]:cursor-not-allowed [&_input]:opacity-70 [&_select]:cursor-not-allowed [&_select]:opacity-70 [&_textarea]:cursor-not-allowed [&_textarea]:opacity-70 [&_[data-stage-mutation]]:hidden"
          : undefined
      }
      data-review-mode={reviewOnly ? stage : undefined}
      onClickCapture={blockMutationClick}
      onKeyDownCapture={blockFormKeyboard}
      onSubmitCapture={blockFormSubmit}
    >
      {reviewOnly ? (
        <div className="border-b border-[#d8d2ca] bg-[#fffdf9] px-5 py-2 text-center text-[10px] font-bold uppercase tracking-[0.18em] text-[#7455b7]">
          Completed - review only
        </div>
      ) : null}
      {children}
    </div>
  );
}
