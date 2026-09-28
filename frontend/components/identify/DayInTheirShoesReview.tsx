"use client";

import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import type { Stakeholder } from "@/lib/stakeholders";
import {
  getStakeholderJourneys,
  saveStakeholderJourneys,
  type StakeholderJourney,
  type Touchpoint
} from "@/lib/stakeholder-journeys";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { UnderstandShell } from "./UnderstandShell";

type DayInTheirShoesReviewProps = {
  assessmentId: string;
};

type Reaction = "Great" | "Fine" | "Painful" | "Unknown";

const journeySteps = [
  "Search",
  "Website",
  "Enquiry",
  "Getting a quote",
  "Purchase",
  "Onboarding",
  "Support",
  "Renewal"
];

const reactions: Reaction[] = ["Great", "Fine", "Painful", "Unknown"];

export function DayInTheirShoesReview({
  assessmentId
}: DayInTheirShoesReviewProps) {
  const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
  const [journeys, setJourneys] = useState<StakeholderJourney[]>([]);
  const [activityStatus, setActivityStatus] = useState<"locked" | "available">(
    "locked"
  );
  const [dependencyMessage, setDependencyMessage] = useState<string | null>(null);
  const [selectedStakeholderId, setSelectedStakeholderId] = useState("");
  const [selectedMoment, setSelectedMoment] = useState(journeySteps[3]);
  const [selectedReaction, setSelectedReaction] = useState<Reaction>("Painful");
  const [note, setNote] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getStakeholderJourneys(assessmentId),
      getIdentifyBoardState(assessmentId)
    ])
      .then(([journeyPayload, boardPayload]) => {
        if (isMounted) {
          setStakeholders(journeyPayload.stakeholders);
          setJourneys(journeyPayload.journeys);
          setActivityStatus(journeyPayload.activity_status);
          setDependencyMessage(journeyPayload.dependency_message);
          setSelectedStakeholderId(journeyPayload.stakeholders[0]?.id ?? "");
          setConfidence(boardPayload.confidence.overall);
          setCoverage(boardPayload.playbookCoverage.slice(0, 6));
          setStatus(journeyPayload.message);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load stakeholder journeys.");
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

  const selectedStakeholder = stakeholders.find(
    (stakeholder) => stakeholder.id === selectedStakeholderId
  );
  const selectedJourney = journeys.find(
    (journey) => journey.stakeholderId === selectedStakeholderId
  );
  const momentsOfTruth = useMemo(
    () =>
      journeys.flatMap((journey) =>
        journey.touchpoints.filter(
          (touchpoint) =>
            touchpoint.painPoints.length > 0 || touchpoint.gaps.length > 0
        )
      ),
    [journeys]
  );
  const touchedMoments = new Set(
    selectedJourney?.touchpoints.map((touchpoint) => touchpoint.moment) ?? []
  );
  const touchpointCount = journeys.reduce(
    (count, journey) => count + journey.touchpoints.length,
    0
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedStakeholder) {
      setError("Select a stakeholder from Who Matters?.");
      return;
    }
    if (!note.trim() && selectedReaction === "Unknown") {
      setError("Add a note for unknown moments so the evidence is meaningful.");
      return;
    }

    const touchpoint = touchpointFromReaction(
      selectedMoment,
      selectedReaction,
      note
    );
    setJourneys((current) =>
      upsertTouchpoint(current, selectedStakeholder, touchpoint)
    );
    setNote("");
    setStatus(null);
    setError(null);
  }

  function handleRemove(journeyId: string, touchpointId: string) {
    setJourneys((current) =>
      current
        .map((journey) =>
          journey.id === journeyId
            ? {
                ...journey,
                touchpoints: journey.touchpoints.filter(
                  (touchpoint) => touchpoint.id !== touchpointId
                )
              }
            : journey
        )
        .filter((journey) => journey.touchpoints.length > 0)
    );
    setStatus(null);
  }

  async function handleSave() {
    if (journeys.length === 0) {
      setError("Add at least one journey moment before saving.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveStakeholderJourneys({
        sessionId: assessmentId,
        journeys
      });
      setJourneys(payload.journeys);
      setActivityStatus(payload.activity_status);
      setDependencyMessage(payload.dependency_message);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save stakeholder journeys.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <UnderstandShell
      assessmentId={assessmentId}
      confidence={confidence}
      coverage={coverage}
    >
      <div className="mx-auto max-w-6xl">
        <p className="text-xs font-bold uppercase tracking-[0.24em] text-purpos-violet">
          03 Understand - A Day in Their Shoes
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-normal">
          Walk the journey as a new customer.
        </h1>

        <div className="mt-5 flex flex-wrap gap-2">
          {stakeholders.length === 0 ? (
            <span className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-500">
              No stakeholders mapped
            </span>
          ) : (
            stakeholders.slice(0, 5).map((stakeholder) => (
              <button
                className={`rounded-full border px-4 py-2 text-sm font-semibold outline-none transition focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2 ${
                  selectedStakeholderId === stakeholder.id
                    ? "border-purpos-violet bg-purpos-violet text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:border-purpos-violet"
                }`}
                disabled={activityStatus === "locked"}
                key={stakeholder.id}
                onClick={() => setSelectedStakeholderId(stakeholder.id)}
                type="button"
              >
                {stakeholder.name}
              </button>
            ))
          )}
        </div>

        {dependencyMessage ? (
          <p className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            {dependencyMessage}
          </p>
        ) : null}

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
              Probable journey - react to each step
            </p>
            <div className="flex gap-3 text-xs font-semibold text-slate-500">
              <LegendDot color="bg-emerald-500" label="Great" />
              <LegendDot color="bg-slate-400" label="Fine" />
              <LegendDot color="bg-[#d98235]" label="Painful" />
            </div>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-8">
            {journeySteps.map((step) => (
              <button
                className="group min-w-0 text-center outline-none"
                disabled={activityStatus === "locked"}
                key={step}
                onClick={() => setSelectedMoment(step)}
                type="button"
              >
                <span className="relative block h-6">
                  <span className="absolute left-1/2 top-1/2 h-px w-full -translate-y-1/2 bg-slate-200 md:left-0" />
                  <span
                    className={`relative mx-auto grid size-6 place-items-center rounded-full border-2 bg-white ${
                      selectedMoment === step
                        ? "border-[#d98235] ring-4 ring-[#d98235]/20"
                        : touchedMoments.has(step)
                          ? "border-emerald-500"
                          : "border-slate-300"
                    }`}
                  >
                    <span
                      className={`size-2 rounded-full ${
                        touchedMoments.has(step)
                          ? "bg-emerald-500"
                          : selectedMoment === step
                            ? "bg-[#d98235]"
                            : "bg-slate-300"
                      }`}
                    />
                  </span>
                </span>
                <span className="mt-3 block truncate text-sm font-bold">
                  {step}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {touchedMoments.has(step) ? "Captured" : "?"}
                </span>
              </button>
            ))}
          </div>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_370px]">
          <form
            className="rounded-md border border-slate-200 bg-white p-5 shadow-sm"
            onSubmit={handleSubmit}
          >
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold tracking-normal">
                {selectedMoment}
              </h2>
              <span className="rounded bg-[#fdebd8] px-2 py-1 text-xs font-bold uppercase tracking-[0.16em] text-[#b55d16]">
                Moment of truth
              </span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {reactions.map((reaction) => (
                <button
                  className={`min-h-10 rounded-md border px-4 text-sm font-bold outline-none transition focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2 ${
                    selectedReaction === reaction
                      ? "border-[#d98235] bg-[#d98235] text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-purpos-violet"
                  }`}
                  disabled={activityStatus === "locked"}
                  key={reaction}
                  onClick={() => setSelectedReaction(reaction)}
                  type="button"
                >
                  {reaction}
                </button>
              ))}
            </div>
            <label className="mt-4 grid gap-2 text-sm font-bold">
              What happened at this step?
              <textarea
                className="min-h-16 resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium outline-none transition disabled:bg-slate-100 focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
                disabled={activityStatus === "locked"}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Took nine days and I had to chase twice..."
                value={note}
              />
            </label>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <button
                className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                disabled={activityStatus === "locked" || isLoading}
                type="submit"
              >
                Add moment
              </button>
              <button
                className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md border border-slate-300 bg-white px-5 text-sm font-bold text-purpos-ink outline-none transition hover:border-purpos-violet hover:text-purpos-violet disabled:cursor-not-allowed disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                disabled={activityStatus === "locked" || isLoading || isSaving}
                data-stage-mutation
                onClick={handleSave}
                type="button"
              >
                {isSaving ? "Saving..." : "Save journeys"}
              </button>
            </div>
            {error ? (
              <p className="mt-3 text-sm font-semibold text-red-700" role="alert">
                {error}
              </p>
            ) : null}
            {status ? (
              <p className="mt-3 text-sm font-semibold text-purpos-violet">
                {status}
              </p>
            ) : null}
          </form>

          <aside className="rounded-md border border-[#c9b9ef] bg-purpos-lilac p-5">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-purpos-violet">
              Moments of truth to investigate
            </p>
            <div className="mt-4 grid gap-3">
              {momentsOfTruth.length === 0 ? (
                <p className="text-sm leading-6 text-slate-600">
                  Painful or unclear moments will collect here.
                </p>
              ) : (
                momentsOfTruth.slice(0, 4).map((touchpoint) => (
                  <div
                    className="rounded-md bg-white px-4 py-3 text-sm font-bold"
                    key={touchpoint.id}
                  >
                    <span className="mr-2 text-[#d98235]">●</span>
                    {touchpoint.moment}
                  </div>
                ))
              )}
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              Evidence mode: just noting where it hurts. No scoring against a
              purpose yet.
            </p>
          </aside>
        </div>

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                Saved locally
              </p>
              <h2 className="mt-1 text-lg font-bold">
                {journeys.length} journey{journeys.length === 1 ? "" : "s"} /{" "}
                {touchpointCount} moment{touchpointCount === 1 ? "" : "s"}
              </h2>
            </div>
            <Link
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
              href={`/assessments/${assessmentId}/identify/where-do-you-stand`}
            >
              Continue to Where Do You Stand
            </Link>
          </div>
          <div className="mt-4 grid gap-3">
            {journeys.map((journey) => (
              <JourneyCard
                journey={journey}
                key={journey.id}
                onRemove={handleRemove}
              />
            ))}
          </div>
        </section>
      </div>
    </UnderstandShell>
  );
}

function touchpointFromReaction(
  moment: string,
  reaction: Reaction,
  note: string
): Touchpoint {
  const trimmedNote = note.trim();
  const noteText = trimmedNote || `${moment} was marked ${reaction}.`;
  return {
    id: crypto.randomUUID(),
    moment,
    expectations: [
      {
        id: crypto.randomUUID(),
        summary: `${moment} should feel ${reaction === "Painful" ? "clear" : "reliable"}.`
      }
    ],
    observedExperiences: [
      {
        id: crypto.randomUUID(),
        summary: noteText,
        supportingEvidence: [reaction]
      }
    ],
    painPoints: reaction === "Painful" ? [noteText] : [],
    gaps:
      reaction === "Painful" || reaction === "Unknown"
        ? [
            {
              id: crypto.randomUUID(),
              summary: `${moment} needs follow-up evidence.`
            }
          ]
        : [],
    opportunities:
      reaction === "Great"
        ? [
            {
              id: crypto.randomUUID(),
              summary: `${moment} may be a strength to preserve.`
            }
          ]
        : [],
    supportingEvidence: [noteText, reaction]
  };
}

function upsertTouchpoint(
  journeys: StakeholderJourney[],
  stakeholder: Stakeholder,
  touchpoint: Touchpoint
): StakeholderJourney[] {
  const existingJourney = journeys.find(
    (journey) => journey.stakeholderId === stakeholder.id
  );
  if (!existingJourney) {
    return [
      ...journeys,
      {
        id: crypto.randomUUID(),
        stakeholderId: stakeholder.id,
        stakeholderName: stakeholder.name,
        touchpoints: [touchpoint],
        supportingEvidence: touchpoint.supportingEvidence,
        sourceActivity: "day-in-their-shoes",
        sourceLabel: "A Day in Their Shoes",
        collectedAt: new Date().toISOString()
      }
    ];
  }

  return journeys.map((journey) =>
    journey.id === existingJourney.id
      ? {
          ...journey,
          touchpoints: [
            ...journey.touchpoints.filter(
              (item) => item.moment !== touchpoint.moment
            ),
            touchpoint
          ],
          supportingEvidence: Array.from(
            new Set([
              ...journey.supportingEvidence,
              ...touchpoint.supportingEvidence
            ])
          )
        }
      : journey
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`size-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}

function JourneyCard({
  journey,
  onRemove
}: {
  journey: StakeholderJourney;
  onRemove: (journeyId: string, touchpointId: string) => void;
}) {
  return (
    <article className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-purpos-violet">
        {journey.sourceLabel}
      </p>
      <h3 className="mt-1 text-base font-semibold">{journey.stakeholderName}</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {journey.touchpoints.map((touchpoint) => (
          <div
            className="rounded-md border border-slate-200 bg-white p-3 text-sm"
            key={touchpoint.id}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="font-bold">{touchpoint.moment}</p>
              <button
                className="text-xs font-bold text-red-700"
                onClick={() => onRemove(journey.id, touchpoint.id)}
                type="button"
              >
                Remove
              </button>
            </div>
            <p className="mt-2 leading-6 text-slate-600">
              {touchpoint.observedExperiences[0]?.summary ??
                touchpoint.supportingEvidence[0] ??
                "Captured"}
            </p>
          </div>
        ))}
      </div>
    </article>
  );
}
