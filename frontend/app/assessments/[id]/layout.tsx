import { AssessmentStageNavigation } from "@/components/assessment/AssessmentStageNavigation";
import { AssessmentPointerRefresher } from "@/components/assessment/AssessmentPointerRefresher";
import type { ReactNode } from "react";

export default async function AssessmentLayout({
  children,
  params
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AssessmentPointerRefresher assessmentId={id}>
      <AssessmentStageNavigation />
      {children}
    </AssessmentPointerRefresher>
  );
}
