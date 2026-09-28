import { CompletedStageReviewBoundary } from "@/components/assessment/CompletedStageReviewBoundary";
import type { ReactNode } from "react";

export default function DefineLayout({ children }: { children: ReactNode }) {
  return (
    <CompletedStageReviewBoundary stage="define">
      {children}
    </CompletedStageReviewBoundary>
  );
}
