import { CompletedStageReviewBoundary } from "@/components/assessment/CompletedStageReviewBoundary";
import type { ReactNode } from "react";

export default function IdentifyLayout({ children }: { children: ReactNode }) {
  return (
    <CompletedStageReviewBoundary stage="identify">
      {children}
    </CompletedStageReviewBoundary>
  );
}
