"use client";

import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import { getListenSummary, type ListenSummaryResponse } from "@/lib/listen-summary";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type ListenSummaryReviewProps = {
  assessmentId: string;
};

export function ListenSummaryReview({ assessmentId }: ListenSummaryReviewProps) {
  const [summary, setSummary] = useState<ListenSummaryResponse | null>(null);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [overall, setOverall] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getListenSummary(assessmentId),
      getIdentifyBoardState(assessmentId)
    ])
      .then(([summaryPayload, boardPayload]) => {
        if (isMounted) {
          setSummary(summaryPayload);
          setCoverage(boardPayload.playbookCoverage);
          setOverall(boardPayload.confidence.overall);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load Listen Summary.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [assessmentId]);

  const confidenceRows = useMemo(() => coverage.slice(0, 6), [coverage]);
  const summaryStats = summary
    ? `${summary.stakeholderCount} stakeholder${
        summary.stakeholderCount === 1 ? "" : "s"
      }, ${summary.hotSeatEvidenceCount} interview evidence update${
        summary.hotSeatEvidenceCount === 1 ? "" : "s"
      }, and ${summary.companyCardsCount} card signal${
        summary.companyCardsCount === 1 ? "" : "s"
      } are now feeding the Identify board.`
    : "Loading Listen evidence.";

  return (
    <div className="min-h-screen bg-[#f2f2f4] text-[#292735]">
      <IdentifyTopBar assessmentId={assessmentId} confidence={overall} />

      <main className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,1fr)_330px]">
        <section className="px-6 py-8 sm:px-10">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
            02 Listen - Complete
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-normal sm:text-4xl">
            Here&apos;s what your people told me.
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {summaryStats}
          </p>

          {error ? (
            <p className="mt-5 text-sm font-medium text-red-700" role="alert">
              {error}
            </p>
          ) : null}

          <section className="mt-8">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
              Areas that moved
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {isLoading ? (
                <SkeletonCards />
              ) : summary && summary.areasMoved.length > 0 ? (
                summary.areasMoved.slice(0, 3).map((area) => (
                  <article
                    className="rounded-md border border-slate-200 bg-white p-4 shadow-sm"
                    key={area.areaId}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="text-sm font-bold">{area.label}</h2>
                      <span className="text-xs font-bold text-[#6f50b5]">
                        {area.status}
                      </span>
                    </div>
                    <div className="mt-4 h-1.5 rounded-full bg-slate-200">
                      <div
                        className="h-1.5 rounded-full bg-[#6f50b5]"
                        style={{
                          width:
                            area.status === "sufficient"
                              ? "85%"
                              : area.status === "partial"
                                ? "45%"
                                : "15%"
                        }}
                      />
                    </div>
                    <p className="mt-3 text-sm leading-5 text-slate-600">
                      {area.note}
                    </p>
                  </article>
                ))
              ) : (
                <p className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 md:col-span-3">
                  {summary?.message ?? "No Listen evidence has moved coverage yet."}
                </p>
              )}
            </div>
          </section>

          <section className="mt-8">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
              What your people said
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {isLoading ? (
                <SkeletonQuoteChips />
              ) : summary?.quotes.length ? (
                summary.quotes.slice(0, 6).map((quote) => (
                  <article
                    className="max-w-xl rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold leading-6 shadow-sm"
                    key={quote.id}
                  >
                    <span className="mr-2 text-[#6f50b5]">●</span>
                    {quote.text}
                    <span className="mt-1 block text-xs font-bold uppercase tracking-[0.16em] text-slate-400">
                      {sourceLabel(quote.sourceActivity)}
                    </span>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-600">
                  Listen evidence will appear here once saved.
                </p>
              )}
            </div>
          </section>

          <section className="mt-10 rounded-md border border-[#c9b9ef] bg-[#eee6fb] p-5">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
              One tension - flagged for Understand
            </p>
            <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <p className="max-w-2xl text-lg font-bold leading-7">
                {summary?.tension ??
                  "No major Listen tension has been flagged yet. Add Hot Seat evidence or Company Cards to sharpen this."}
              </p>
              <Link
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#6f50b5] px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                href={`/assessments/${assessmentId}/identify`}
              >
                Back to board <span aria-hidden="true" className="ml-2">-&gt;</span>
              </Link>
            </div>
          </section>
        </section>

        <aside className="border-l border-slate-200 bg-white px-6 py-8">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
            Confidence scorecard
          </p>
          <div className="mt-4 flex items-end gap-3">
            <p className="text-5xl font-bold leading-none">{overall}%</p>
            <p className="pb-1 text-sm leading-4 text-slate-600">
              confident
              <br />
              across {confidenceRows.length} areas
            </p>
          </div>
          <div className="mt-5 h-1.5 rounded-full bg-slate-200">
            <div
              className="h-1.5 rounded-full bg-[#6f50b5]"
              style={{ width: `${overall}%` }}
            />
          </div>

          <div className="mt-7 grid gap-4">
            {confidenceRows.length > 0 ? confidenceRows.map((item) => {
              const value =
                item.status === "sufficient"
                  ? 80
                  : item.status === "partial"
                    ? 45
                    : 10;
              return (
                <div key={item.areaId}>
                  <div className="flex justify-between gap-3 text-sm">
                    <span>{item.label}</span>
                    <span className="text-xs text-[#6f50b5]">{value}%</span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-slate-200">
                    <div
                      className="h-1.5 rounded-full bg-[#6f50b5]"
                      style={{ width: `${value}%` }}
                    />
                  </div>
                </div>
              );
            }) : (
              <p className="rounded-md border border-dashed border-slate-300 p-3 text-sm leading-6 text-slate-600">
                Confidence coverage will appear once Listen evidence is saved.
              </p>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}

function IdentifyTopBar({
  assessmentId,
  confidence
}: {
  assessmentId: string;
  confidence: number;
}) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="flex min-h-16 items-center justify-between gap-4 px-5 sm:px-8">
        <Link
          className="flex items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
          href={`/assessments/${assessmentId}/identify`}
        >
          <span className="grid size-8 place-items-center rounded-md bg-[#6f50b5] text-sm font-bold text-white">
            P
          </span>
          <span className="text-base font-bold">PurpOS</span>
        </Link>
        <div className="hidden items-center gap-4 text-sm md:flex">
          <span className="font-semibold tracking-[0.18em] text-slate-500">
            IDENTIFY
          </span>
          <span className="text-slate-300">01 Discover</span>
          <span className="font-semibold text-[#6f50b5]">02 Listen</span>
          <span className="text-slate-300">03 Understand</span>
          <span className="rounded-full border border-slate-200 px-3 py-1 font-semibold">
            <span className="mr-2 text-[#6f50b5]">●</span>
            Confidence {confidence}%
          </span>
        </div>
      </nav>
    </header>
  );
}

function SkeletonCards() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div
          className="h-28 animate-pulse rounded-md border border-slate-200 bg-white"
          key={item}
        />
      ))}
    </>
  );
}

function SkeletonQuoteChips() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <div
          className="h-16 w-full max-w-xl animate-pulse rounded-md border border-slate-200 bg-white sm:w-64"
          key={item}
        />
      ))}
    </>
  );
}

function sourceLabel(sourceActivity: string) {
  if (sourceActivity === "who-matters") {
    return "Who Matters";
  }
  if (sourceActivity === "hot-seat") {
    return "Hot Seat";
  }
  if (sourceActivity === "company-cards") {
    return "Company Cards";
  }
  return "Listen";
}
