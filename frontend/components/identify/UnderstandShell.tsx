"use client";

import type { PlaybookCoverage } from "@/lib/identify-board";
import Link from "next/link";
import type { ReactNode } from "react";

type UnderstandShellProps = {
  assessmentId: string;
  confidence: number;
  coverage: PlaybookCoverage[];
  coverageTotal?: number;
  metricLabel?: "confidence" | "evidence-coverage";
  children: ReactNode;
};

export function UnderstandShell({
  assessmentId,
  confidence,
  coverage,
  coverageTotal = coverage.length,
  metricLabel = "confidence",
  children
}: UnderstandShellProps) {
  const showsEvidenceCoverage = metricLabel === "evidence-coverage";

  return (
    <div className="min-h-screen bg-[#f4f3f6] text-purpos-ink">
      <header className="border-b border-slate-200 bg-white">
        <nav className="flex min-h-16 items-center justify-between gap-4 px-5 sm:px-8">
          <div className="flex min-w-0 items-center gap-5">
            <Link
              className="flex shrink-0 items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
              href={`/assessments/${assessmentId}/identify`}
            >
              <span className="grid size-8 place-items-center rounded-md bg-purpos-violet text-sm font-bold text-white">
                P
              </span>
              <span className="text-base font-bold">PurpOS</span>
            </Link>
            <div className="hidden items-center gap-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 md:flex">
              <span>Identify</span>
              <span className="text-slate-300">&gt;</span>
              <span>01 Discover</span>
              <span className="text-slate-300">&gt;</span>
              <span>02 Listen</span>
              <span className="text-slate-300">&gt;</span>
              <span className="text-purpos-violet">03 Understand</span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-4">
            <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 sm:flex">
              <span className="size-2 rounded-full bg-purpos-violet" />
              {showsEvidenceCoverage ? "Evidence coverage" : "Confidence"} {confidence}%
            </div>
            <span className="size-10 rounded-full bg-slate-200" />
          </div>
        </nav>
      </header>

      <main className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,1fr)_310px]">
        <section className="px-5 py-8 sm:px-10">{children}</section>
        <aside className="border-l border-slate-200 bg-white px-6 py-8">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
            {showsEvidenceCoverage ? "Identify evidence coverage" : "Confidence scorecard"}
          </p>
          <p className="mt-4 text-5xl font-bold leading-none">{confidence}%</p>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {showsEvidenceCoverage
              ? `Overall coverage across the ${coverageTotal} Identify evidence areas.`
              : `Confident across ${coverage.length} areas.`}
          </p>
          <div className="mt-5 h-1.5 rounded-full bg-slate-200">
            <div
              className="h-1.5 rounded-full bg-purpos-violet"
              style={{ width: `${confidence}%` }}
            />
          </div>
          {showsEvidenceCoverage ? (
            <div className="mt-7">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
                Coverage status preview
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Showing {coverage.length} of {coverageTotal} evidence areas
              </p>
            </div>
          ) : null}
          <div className={showsEvidenceCoverage ? "mt-4 grid gap-3" : "mt-7 grid gap-4"}>
            {coverage.map((item) => (
              <div key={item.areaId}>
                <div className="flex justify-between gap-3 text-sm">
                  <span>{item.label}</span>
                  <span
                    className={
                      showsEvidenceCoverage
                        ? "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold capitalize text-slate-600"
                        : "text-xs text-purpos-violet"
                    }
                  >
                    {showsEvidenceCoverage
                      ? item.status
                      : `${coveragePercent(item.status)}%`}
                  </span>
                </div>
                {!showsEvidenceCoverage ? (
                  <div className="mt-2 h-1.5 rounded-full bg-slate-200">
                    <div
                      className="h-1.5 rounded-full bg-purpos-violet"
                      style={{ width: `${coveragePercent(item.status)}%` }}
                    />
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </aside>
      </main>
    </div>
  );
}

export function coveragePercent(status: PlaybookCoverage["status"]) {
  if (status === "sufficient") {
    return 75;
  }
  if (status === "partial") {
    return 50;
  }
  return 20;
}

export function sourceStage(sourceActivity: string | null) {
  if (
    sourceActivity === "ai-detective" ||
    sourceActivity === "signal-hunt" ||
    sourceActivity === "discover-synthesis"
  ) {
    return "Discover";
  }
  if (
    sourceActivity === "who-matters" ||
    sourceActivity === "hot-seat" ||
    sourceActivity === "company-cards" ||
    sourceActivity === "listen-summary"
  ) {
    return "Listen";
  }
  return "Understand";
}
