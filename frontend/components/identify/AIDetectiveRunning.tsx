"use client";

import {
  collectAIDetectiveFindings,
  getAIDetective,
  type AIDetectiveResponse,
  type ExternalResearchCategory
} from "@/lib/ai-detective";
import {
  getIdentifyBoardState,
  type IdentifyBoardState
} from "@/lib/identify-board";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { IdentifyJourneyHeader } from "./IdentifyJourneyHeader";

type AIDetectiveRunningProps = {
  assessmentId: string;
};

type RunStepStatus =
  | "running"
  | "done"
  | "issue"
  | "unavailable"
  | "not-configured"
  | "not-scanned";

const researchCategoryLabels: Record<string, string> = {
  website: "Website & page copy",
  "products-services": "Products & services",
  "leadership-values-purpose": "Leadership, values & purpose",
  "sustainability-impact": "Sustainability claims",
  competitors: "Competitors",
  "customer-groups": "Customer groups",
  "market-sector-trends": "Market & sector trends",
  "reviews-ratings": "Reviews & ratings",
  "press-mentions": "Press & mentions"
};

export function AIDetectiveRunning({
  assessmentId
}: AIDetectiveRunningProps) {
  const hasStarted = useRef(false);
  const [boardState, setBoardState] = useState<IdentifyBoardState | null>(null);
  const [detectiveResult, setDetectiveResult] =
    useState<AIDetectiveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCollecting, setIsCollecting] = useState(true);

  const runDetective = useCallback(async (forceCollect = false) => {
    setIsCollecting(true);
    setDetectiveResult(null);
    setError(null);

    try {
      const initialBoard = await getIdentifyBoardState(assessmentId);
      setBoardState(initialBoard);
      const savedActivity = initialBoard.activities.find(
        (activity) => activity.activityId === "ai-detective"
      );

      if (!forceCollect && savedActivity?.status === "completed") {
        setDetectiveResult(await getAIDetective(assessmentId));
        return;
      }

      const result = await collectAIDetectiveFindings(assessmentId, {
        refresh: forceCollect
      });
      setDetectiveResult(result);
      const refreshedBoard = await getIdentifyBoardState(assessmentId);
      setBoardState(refreshedBoard);

    } catch {
      setError("I couldn't complete the AI Detective run.");
    } finally {
      setIsCollecting(false);
    }
  }, [assessmentId]);

  useEffect(() => {
    if (hasStarted.current) {
      return;
    }
    hasStarted.current = true;

    void runDetective();

  }, [runDetective]);

  const organisation = boardState?.organisation;
  const companyName = organisation?.companyName ?? "your organisation";
  const website = organisation?.website ?? null;
  const researchStatus = detectiveResult?.research_status;
  const findingsCount = detectiveResult?.progress.findingsCount ?? 0;
  const canContinue = Boolean(detectiveResult || error);
  const isSuccessful =
    researchStatus === "connected" ||
    (researchStatus === "idle" && findingsCount > 0);
  const canRetry = !isCollecting && !isSuccessful;

  return (
    <main className="min-h-screen bg-[#f4efe8] text-purpos-ink">
      <IdentifyJourneyHeader
        assessmentId={assessmentId}
        backHref="/identify/who-are-you"
        confidence={boardState?.confidence.overall ?? null}
        current="discover"
      />

      <section className="px-5 py-10 sm:px-8 lg:py-14">
        <div className="mx-auto max-w-6xl">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#d67832]">
            01 Discover · AI Detective
          </p>
          <h1 className="mt-5 text-4xl font-bold tracking-normal text-[#29272d] sm:text-5xl">
            I&apos;m investigating on my own.
          </h1>
          <p className="mt-4 max-w-3xl text-lg leading-7 text-[#69615b]">
            I&apos;m retrieving permitted public website sources for {companyName}
            and turning them into findings you can review. Unsupported external
            sources remain clearly marked as not scanned.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-3">
              <InfoPill label="Company" value={companyName} />
              {website ? <InfoPill label="Web" value={website} /> : null}
            </div>
            <Link
              className="self-start text-sm font-semibold text-purpos-violet underline decoration-purpos-violet/35 underline-offset-4"
              href="/identify/who-are-you"
            >
              Edit inputs
            </Link>
          </div>

          <section className="mt-7 border border-[#d5cec7] bg-[#fffdf9] p-5 shadow-sm sm:p-8">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#817870]">
                  Investigation status
                </p>
                <h2 className="mt-2 text-2xl font-bold tracking-normal">
                  {isCollecting ? "Investigating..." : statusHeadline(researchStatus)}
                </h2>
              </div>
              <p className="text-sm font-semibold text-[#69615b]">
                {findingsCount} finding{findingsCount === 1 ? "" : "s"} saved
              </p>
            </div>

            <div className="mt-8 grid gap-x-10 md:grid-cols-2">
              {(detectiveResult?.externalResearch.categories ?? []).map((category) => (
                <SourceRow
                  key={category.category}
                  label={researchCategoryLabels[category.category] ?? category.category}
                  status={categoryStatus(category, isCollecting)}
                />
              ))}
              {detectiveResult ? null : (
                <>
                  <SourceRow
                    label="Website & page copy"
                    status={website ? "running" : "not-scanned"}
                  />
                  <SourceRow label="Broader public search" status="not-scanned" />
                </>
              )}
              <SourceRow
                label="AI synthesis of retrieved sources"
                status={
                  isCollecting ? "running" : isSuccessful ? "done" : "issue"
                }
              />
            </div>

            {detectiveResult?.message ? (
              <p className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                {detectiveResult.message}
              </p>
            ) : null}
            {detectiveResult?.progress.limitation ? (
              <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                {detectiveResult.progress.limitation}
              </p>
            ) : null}
            {error ? (
              <p className="mt-8 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-800">
                {error}
              </p>
            ) : null}

            <div className="mt-9 flex flex-wrap items-center justify-between gap-3 border-t border-[#ddd6cf] pt-6">
              {canRetry ? (
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-lg border border-purpos-violet bg-white px-6 text-base font-semibold text-purpos-violet outline-none transition hover:bg-purpos-lilac focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                  data-stage-mutation
                  onClick={() => void runDetective(true)}
                  type="button"
                >
                  Retry investigation
                </button>
              ) : null}
              <Link
                className={`inline-flex min-h-12 items-center justify-center px-1 text-base font-semibold text-purpos-violet underline decoration-purpos-violet/35 underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-purpos-violet ${
                  canContinue
                    ? ""
                    : "pointer-events-none text-slate-400"
                }`}
                href={`/assessments/${assessmentId}/identify`}
                aria-disabled={!canContinue}
              >
                See the investigation board
                <span aria-hidden="true" className="ml-3">
                  -&gt;
                </span>
              </Link>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[#d5cec7] bg-[#fffdf9] px-5 py-3">
      <span className="mr-3 text-[10px] font-bold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <span className="text-base font-semibold text-slate-700">{value}</span>
    </div>
  );
}

function SourceRow({
  label,
  status
}: {
  label: string;
  status: RunStepStatus;
}) {
  return (
    <div className="grid min-h-14 grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-[#e4ddd6] py-3">
      <span
        aria-hidden="true"
        className={`grid size-5 place-items-center rounded-full border ${
          status === "done"
            ? "border-purpos-violet bg-purpos-lilac text-purpos-violet"
            : status === "running"
              ? "border-purpos-violet"
              : status === "issue"
                ? "border-amber-300 bg-amber-50"
                : status === "unavailable"
                  ? "border-red-300 bg-red-50"
                  : status === "not-configured"
                    ? "border-slate-300 bg-slate-50"
                    : "border-slate-300"
        }`}
      >
        {status === "done" ? "OK" : null}
      </span>
      <span
        className={`text-base font-semibold ${
          status === "not-scanned" || status === "not-configured"
            ? "text-slate-500"
            : "text-purpos-ink"
        }`}
      >
        {label}
      </span>
      <span className="text-xs font-medium text-slate-500">
        {stepLabel(status)}
      </span>
    </div>
  );
}

function statusHeadline(
  status: AIDetectiveResponse["research_status"] | undefined
) {
  if (status === "connected") {
    return "Investigation saved.";
  }
  if (status === "limited") {
    return "Limited evidence available.";
  }
  if (status === "unavailable") {
    return "Website unavailable.";
  }
  if (status === "not-configured") {
    return "Research not configured.";
  }
  if (status === "error") {
    return "Investigation needs a retry.";
  }
  return "Investigation complete.";
}

function stepLabel(status: RunStepStatus) {
  if (status === "done") {
    return "done";
  }
  if (status === "running") {
    return "scanning...";
  }
  if (status === "issue") {
    return "needs review";
  }
  if (status === "unavailable") {
    return "unavailable";
  }
  if (status === "not-configured") {
    return "not configured";
  }
  if (status === "not-scanned") {
    return "not scanned";
  }
  return "waiting";
}

function categoryStatus(
  category: ExternalResearchCategory,
  isCollecting: boolean
): RunStepStatus {
  if (isCollecting && category.status === "not-scanned") {
    return "running";
  }
  if (category.status === "done") {
    return "done";
  }
  if (category.status === "unavailable") {
    return "unavailable";
  }
  if (category.status === "not-configured") {
    return "not-configured";
  }
  if (category.status === "not-scanned") {
    return "not-scanned";
  }
  return "issue";
}
