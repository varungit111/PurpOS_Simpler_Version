"use client";

import {
  buildAssessmentStageNavigation,
  type AssessmentStageNavigationItem
} from "@/lib/assessment-stage-navigation";
import Link from "next/link";
import { useAssessmentSession } from "./AssessmentSessionContext";

export function AssessmentStageNavigation() {
  const session = useAssessmentSession();
  const stages = buildAssessmentStageNavigation(session);

  return (
    <div className="border-b border-[#d8d2ca] bg-[#fffdf9] text-[#292624]">
      <nav
        aria-label="Assessment stages"
        className="mx-auto max-w-[1760px] overflow-x-auto [scrollbar-width:none]"
      >
        <ol className="grid min-w-[620px] grid-cols-5 px-4 sm:px-8 lg:px-14">
          {stages.map((stage) => (
            <li
              className="border-r border-[#e1dbd4] last:border-r-0"
              key={stage.id}
            >
              <StageItem stage={stage} />
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
}

function StageItem({ stage }: { stage: AssessmentStageNavigationItem }) {
  const content = (
    <>
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9a9189]">
        {stage.position}
      </span>
      <span className="mt-0.5 text-xs font-bold uppercase tracking-[0.16em] sm:text-sm">
        {stage.label}
      </span>
      <span className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.12em]">
        {stage.state === "current"
          ? "Current"
          : stage.state === "completed"
            ? "Review"
            : stage.id === "measure"
              ? "Unavailable"
              : "Not started"}
      </span>
    </>
  );

  if (stage.href) {
    return (
      <Link
        aria-current={stage.state === "current" ? "step" : undefined}
        className={`flex min-h-[68px] flex-col justify-center border-b-2 px-3 py-2 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#7455b7] sm:px-5 ${
          stage.state === "current"
            ? "border-[#7455b7] text-[#7455b7]"
            : "border-transparent text-[#5f5853] hover:border-[#b8a5d4] hover:text-[#7455b7]"
        }`}
        href={stage.href}
      >
        {content}
      </Link>
    );
  }

  return (
    <span
      aria-disabled="true"
      className="flex min-h-[68px] cursor-not-allowed flex-col justify-center border-b-2 border-transparent px-3 py-2 text-[#aaa29b] sm:px-5"
    >
      {content}
    </span>
  );
}
