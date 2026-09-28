"use client";

import {
  identifyDemoActivities,
  type IdentifyActivity
} from "@/data/identify-investigation";
import {
  getIdentifyBoardState,
  type IdentifyBoardState
} from "@/lib/identify-board";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { IdentifyJourneyHeader } from "./IdentifyJourneyHeader";
import { InvestigationCard } from "./InvestigationCard";

const boardActivityIds = [
  "ai-detective",
  "signal-hunt",
  "who-matters",
  "hot-seat",
  "company-cards",
  "day-in-their-shoes",
  "where-do-you-stand",
  "perception-gaps",
  "evidence-wall"
] as const;

type IdentifyInvestigationBoardProps = {
  assessmentId?: string;
};

export function IdentifyInvestigationBoard({
  assessmentId
}: IdentifyInvestigationBoardProps) {
  const [boardState, setBoardState] = useState<IdentifyBoardState | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(assessmentId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    if (!assessmentId) {
      setIsLoading(false);
      return;
    }

    getIdentifyBoardState(assessmentId)
      .then((payload) => {
        if (isMounted) {
          setBoardState(payload);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load the latest Investigation Board state.");
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

  const activities = useMemo(
    () => buildBoardActivities(boardState),
    [boardState]
  );
  const completed = activities.filter(
    (activity) => activity.status === "completed"
  ).length;
  const progress = activities.length
    ? Math.round((completed / activities.length) * 100)
    : 0;
  const identifyBrief = boardState?.activities.find(
    (activity) => activity.activityId === "identify-brief"
  );
  const organisationName =
    boardState?.organisation.companyName ?? "Your business";
  const boardHref = assessmentId
    ? `/assessments/${assessmentId}/identify`
    : "/identify/who-are-you";

  return (
    <div className="min-h-screen bg-[#f4efe8] text-purpos-ink">
      {assessmentId ? (
        <IdentifyJourneyHeader
          assessmentId={assessmentId}
          backHref={`/assessments/${assessmentId}/identify/ai-detective`}
          confidence={boardState?.confidence.overall ?? null}
          current="board"
        />
      ) : null}

      <main className="px-5 py-8 sm:px-8 lg:py-10">
        <div className="mx-auto grid max-w-[1500px] gap-8 xl:grid-cols-[300px_minmax(0,1fr)] xl:gap-10">
          <aside className="flex flex-col border-b border-[#d5cec7] pb-8 xl:min-h-[760px] xl:border-b-0 xl:border-r xl:pb-0 xl:pr-8">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#817870]">
                The business · what I know so far
              </p>
              <h1 className="mt-5 break-words text-4xl font-semibold leading-tight tracking-normal">
                {organisationName}
              </h1>
              {boardState?.organisation.website ? (
                <p className="mt-3 break-all text-sm font-medium text-[#746b64]">
                  {boardState.organisation.website}
                </p>
              ) : null}
              <p className="mt-6 text-base leading-7 text-[#625b56]">
                This board reflects the organisation context, saved Identify
                evidence, and activity state for this assessment.
              </p>
            </div>

            {error ? (
              <p className="mt-6 border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-800">
                {error}
              </p>
            ) : null}
            {isLoading ? (
              <p className="mt-6 border border-[#d5cec7] bg-[#fffdf9] p-4 text-sm font-medium text-[#69615b]">
                Loading the latest saved board...
              </p>
            ) : null}

            <div className="mt-10 grid gap-7 sm:grid-cols-2 xl:mt-auto xl:grid-cols-1">
              <section aria-label="Identify confidence">
                <div className="flex items-baseline justify-between gap-4">
                  <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-[#817870]">
                    Confidence
                  </h2>
                  <span className="text-lg font-semibold">
                    {boardState
                      ? `${boardState.confidence.overall}%`
                      : "Building"}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#746b64]">
                  Based on saved coverage across the 20 Identify evidence areas.
                </p>
              </section>

              <section aria-label="Identify progress">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-[#817870]">
                    Progress
                  </h2>
                  <span className="text-sm font-semibold">
                    {completed} of {boardActivityIds.length}
                  </span>
                </div>
                <div className="mt-3 h-2 overflow-hidden bg-[#ddd5cd]">
                  <div
                    className="h-full bg-purpos-violet"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </section>

              <section
                aria-label="Identify Brief status"
                className="border-t border-[#d5cec7] pt-6 sm:col-span-2 xl:col-span-1"
                id="identify-brief"
              >
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#817870]">
                  Identify Brief
                </p>
                <p className="mt-2 text-lg font-semibold">
                  {identifyBrief?.status === "locked"
                    ? "Locked"
                    : identifyBrief?.status === "completed"
                      ? "Ready to review"
                      : identifyBrief
                        ? "In progress"
                        : "Waiting for saved state"}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#746b64]">
                  {identifyBrief?.progressLabel ??
                    "Complete the required Identify evidence before handoff."}
                </p>
                {assessmentId && identifyBrief?.status !== "locked" ? (
                  <Link
                    className="mt-4 inline-flex min-h-10 items-center font-semibold text-purpos-violet underline decoration-purpos-violet/35 underline-offset-4"
                    href={`/assessments/${assessmentId}/identify/brief`}
                  >
                    Open Identify Brief -&gt;
                  </Link>
                ) : null}
              </section>
            </div>
          </aside>

          <section aria-label="Identify activities">
            <div className="flex items-end justify-between gap-4 border-b border-[#d5cec7] pb-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#817870]">
                  Investigation Board
                </p>
                <p className="mt-1 text-sm text-[#746b64]">
                  Activity states come from the latest saved assessment.
                </p>
              </div>
              <Link
                className="hidden text-sm font-semibold text-purpos-violet underline decoration-purpos-violet/35 underline-offset-4 sm:block"
                href={boardHref}
              >
                Refresh board
              </Link>
            </div>

            {!isLoading && !error ? (
              <div className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {activities.map((activity, index) => {
                  const firstInSection =
                    activities.findIndex(
                      (candidate) => candidate.section === activity.section
                    ) === index;
                  return (
                    <div
                      className="min-w-0"
                      id={firstInSection ? activity.section : undefined}
                      key={activity.id}
                    >
                      <InvestigationCard
                        activity={activity}
                        assessmentId={assessmentId}
                      />
                    </div>
                  );
                })}
              </div>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}

function buildBoardActivities(
  boardState: IdentifyBoardState | null
): IdentifyActivity[] {
  if (!boardState) {
    return [];
  }

  const liveActivityById = new Map(
    boardState.activities.map((activity) => [activity.activityId, activity])
  );
  const metadataById = new Map(
    identifyDemoActivities.map((activity) => [activity.id, activity])
  );

  return boardActivityIds.flatMap((activityId) => {
    const metadata = metadataById.get(activityId);
    const liveActivity = liveActivityById.get(activityId);
    if (!metadata || !liveActivity) {
      return [];
    }

    return [
      {
        ...metadata,
        status: liveActivity.status,
        progressLabel: liveActivity.progressLabel,
        helperText: liveActivity.progressLabel ?? metadata.helperText,
        actionLabel: actionLabelForStatus(liveActivity.status, metadata)
      }
    ];
  });
}

function actionLabelForStatus(
  status: IdentifyActivity["status"],
  activity: IdentifyActivity
) {
  if (status === "locked") {
    return undefined;
  }
  if (status === "completed") {
    return "Review";
  }
  if (status === "ai-running") {
    return "View";
  }
  if (status === "conditional") {
    return activity.id === "signal-hunt" ? "Review" : "Open";
  }
  if (status === "invite-team") {
    return "Set up";
  }
  return "Start";
}
