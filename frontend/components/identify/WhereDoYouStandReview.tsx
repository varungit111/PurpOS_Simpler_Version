"use client";

import { positioningPrompts } from "@/data/where-do-you-stand";
import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import {
  getWhereDoYouStand,
  saveWhereDoYouStand,
  type PositioningEvidenceResponse
} from "@/lib/where-do-you-stand";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { UnderstandShell } from "./UnderstandShell";

type WhereDoYouStandReviewProps = {
  assessmentId: string;
};

const spectrumLabels = ["Cause", "Personality", "Approach", "Offer", "Presence"];
const defaultTodayIndex = 3;
const defaultAimIndex = 2;
const defaultContributionIndex = 3;
const contributionSteps = [
  { title: "Charity", detail: "One-off giving" },
  { title: "Philanthropy", detail: "Ongoing giving" },
  { title: "Responsibility", detail: "Do no harm" },
  { title: "Shared value", detail: "Doing good is how you make money" },
  { title: "Built-in", detail: "The whole business exists to help" }
];

export function WhereDoYouStandReview({
  assessmentId
}: WhereDoYouStandReviewProps) {
  const [todayIndex, setTodayIndex] = useState(defaultTodayIndex);
  const [aimIndex, setAimIndex] = useState(defaultAimIndex);
  const [contributionIndex, setContributionIndex] = useState(
    defaultContributionIndex
  );
  const [positioningNote, setPositioningNote] = useState("");
  const [contributionNote, setContributionNote] = useState("");
  const [responses, setResponses] = useState<PositioningEvidenceResponse[]>([]);
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getWhereDoYouStand(assessmentId),
      getIdentifyBoardState(assessmentId)
    ])
      .then(([standingPayload, boardPayload]) => {
        if (isMounted) {
          const loadedResponses = standingPayload.evidence?.responses ?? [];
          const current = loadedResponses.find(
            (response) => response.topic === "current-positioning"
          );
          const desired = loadedResponses.find(
            (response) => response.topic === "current-vs-desired"
          );
          const contribution = loadedResponses.find(
            (response) => response.topic === "social-contribution"
          );
          setResponses(loadedResponses);
          if (current) {
            setTodayIndex(indexFromText(current.response, defaultTodayIndex));
            setPositioningNote(current.supportingEvidence.join(", "));
          }
          if (desired) {
            setAimIndex(indexFromText(desired.response, defaultAimIndex));
          }
          if (contribution) {
            setContributionIndex(
              indexFromText(contribution.response, defaultContributionIndex)
            );
            setContributionNote(contribution.supportingEvidence.join(", "));
          }
          setConfidence(boardPayload.confidence.overall);
          setCoverage(boardPayload.playbookCoverage.slice(0, 6));
          setStatus(standingPayload.message);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load Where Do You Stand.");
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

  const evidencePreview = useMemo(
    () => responses.slice(0, 4),
    [responses]
  );

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    setStatus(null);

    const nextResponses = buildResponses({
      todayIndex,
      aimIndex,
      contributionIndex,
      positioningNote,
      contributionNote
    });

    try {
      const payload = await saveWhereDoYouStand({
        sessionId: assessmentId,
        responses: nextResponses
      });
      setResponses(payload.evidence?.responses ?? []);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save Where Do You Stand evidence.");
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
          03 Understand - Where Do You Stand
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-normal">
          Where you stand - and where you want to.
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Two quick reads. Mark where the organisation sits today, and where it
          should sit next.
        </p>

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <h2 className="text-lg font-bold tracking-normal">
              Positioning spectrum
            </h2>
            <p className="text-sm text-slate-500">what you lead with</p>
          </div>
          <div className="mt-8">
            <div className="mb-8 flex items-center justify-between text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
              <span>Intangible - meaning</span>
              <span>Tangible - product</span>
            </div>
            <div className="relative mx-auto max-w-4xl">
              <div className="absolute left-0 right-0 top-3 h-px bg-slate-200" />
              <div className="grid grid-cols-5 gap-2">
                {spectrumLabels.map((label, index) => (
                  <button
                    className="relative grid gap-4 text-center outline-none"
                    key={label}
                    onClick={() => setTodayIndex(index)}
                    type="button"
                  >
                    {aimIndex === index ? (
                      <span className="absolute -top-7 left-1/2 -translate-x-1/2 rounded-full bg-purpos-violet px-3 py-1 text-xs font-bold text-white">
                        Aim
                      </span>
                    ) : null}
                    {todayIndex === index ? (
                      <span className="absolute -top-7 left-1/2 -translate-x-1/2 rounded-full bg-purpos-ink px-3 py-1 text-xs font-bold text-white">
                        Today
                      </span>
                    ) : null}
                    <span
                      className={`relative mx-auto grid size-6 place-items-center rounded-full border-2 bg-white ${
                        todayIndex === index
                          ? "border-purpos-ink"
                          : aimIndex === index
                            ? "border-purpos-violet ring-4 ring-purpos-violet/20"
                            : "border-slate-300"
                      }`}
                    >
                      <span
                        className={`size-2 rounded-full ${
                          todayIndex === index
                            ? "bg-purpos-ink"
                            : aimIndex === index
                              ? "bg-purpos-violet"
                              : "bg-slate-300"
                        }`}
                      />
                    </span>
                    <span className="text-sm font-bold">{label}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-8 flex flex-wrap gap-2">
              {spectrumLabels.map((label, index) => (
                <button
                  className={`rounded-md border px-3 py-2 text-sm font-bold ${
                    aimIndex === index
                      ? "border-purpos-violet bg-purpos-lilac text-purpos-violet"
                      : "border-slate-200 bg-white text-slate-600"
                  }`}
                  key={label}
                  onClick={() => setAimIndex(index)}
                  type="button"
                >
                  Aim: {label}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <h2 className="text-lg font-bold tracking-normal">
              How you give back
            </h2>
            <p className="text-sm text-slate-500">
              from doing good on the side, to good built into the business
            </p>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-5">
            {contributionSteps.map((step, index) => (
              <button
                className={`relative min-h-28 rounded-md border p-4 text-left outline-none transition focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2 ${
                  contributionIndex === index
                    ? "border-purpos-violet bg-purpos-lilac"
                    : "border-slate-200 bg-white hover:border-purpos-violet"
                }`}
                key={step.title}
                onClick={() => setContributionIndex(index)}
                type="button"
              >
                {contributionIndex === index ? (
                  <span className="absolute -top-3 left-4 rounded-full bg-purpos-violet px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white">
                    You are here
                  </span>
                ) : null}
                <span className="text-xs font-bold text-slate-400">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="mt-3 block text-base font-bold">
                  {step.title}
                </span>
                <span className="mt-2 block text-sm leading-5 text-slate-600">
                  {step.detail}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="mt-5 grid gap-4 rounded-md border border-slate-200 bg-white p-5 shadow-sm lg:grid-cols-2">
          <label className="grid gap-2 text-sm font-bold">
            Positioning evidence note
            <textarea
              className="min-h-20 resize-none rounded-md border border-slate-300 px-3 py-2 text-sm font-medium outline-none focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
              onChange={(event) => setPositioningNote(event.target.value)}
              placeholder="What evidence makes today's position feel true?"
              value={positioningNote}
            />
          </label>
          <label className="grid gap-2 text-sm font-bold">
            Contribution evidence note
            <textarea
              className="min-h-20 resize-none rounded-md border border-slate-300 px-3 py-2 text-sm font-medium outline-none focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
              onChange={(event) => setContributionNote(event.target.value)}
              placeholder="What proof supports this contribution level?"
              value={contributionNote}
            />
          </label>
          <div className="lg:col-span-2 flex flex-col gap-3 sm:flex-row">
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
              disabled={isLoading || isSaving}
              data-stage-mutation
              onClick={handleSave}
              type="button"
            >
              {isSaving ? "Saving..." : "Save positioning evidence"}
            </button>
            <Link
              className="inline-flex min-h-11 items-center justify-center rounded-md border border-slate-300 bg-white px-5 text-sm font-bold text-purpos-ink outline-none transition hover:border-purpos-violet hover:text-purpos-violet focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
              href={`/assessments/${assessmentId}/identify/perception-gaps`}
            >
              Continue to Perception Gaps
            </Link>
          </div>
          {error ? (
            <p className="text-sm font-semibold text-red-700" role="alert">
              {error}
            </p>
          ) : null}
          {status ? (
            <p className="text-sm font-semibold text-purpos-violet">{status}</p>
          ) : null}
        </section>

        {evidencePreview.length > 0 ? (
          <section className="mt-5 grid gap-3 md:grid-cols-2">
            {evidencePreview.map((response) => (
              <article
                className="rounded-md border border-slate-200 bg-white p-4 text-sm shadow-sm"
                key={response.id}
              >
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-purpos-violet">
                  {response.topic}
                </p>
                <p className="mt-2 leading-6 text-slate-700">
                  {response.response}
                </p>
              </article>
            ))}
          </section>
        ) : null}
      </div>
    </UnderstandShell>
  );
}

function buildResponses({
  aimIndex,
  contributionIndex,
  contributionNote,
  positioningNote,
  todayIndex
}: {
  aimIndex: number;
  contributionIndex: number;
  contributionNote: string;
  positioningNote: string;
  todayIndex: number;
}): PositioningEvidenceResponse[] {
  const currentPrompt = promptFor("current-positioning");
  const desiredPrompt = promptFor("current-vs-desired");
  const contributionPrompt = promptFor("social-contribution");
  return [
    {
      id: crypto.randomUUID(),
      topic: "current-positioning",
      prompt: currentPrompt.prompt,
      response: `Today the organisation leads with ${spectrumLabels[todayIndex]}.`,
      supportingEvidence: splitList(positioningNote)
    },
    {
      id: crypto.randomUUID(),
      topic: "current-vs-desired",
      prompt: desiredPrompt.prompt,
      response: `The aim is to shift toward ${spectrumLabels[aimIndex]}.`,
      supportingEvidence: splitList(positioningNote)
    },
    {
      id: crypto.randomUUID(),
      topic: "social-contribution",
      prompt: contributionPrompt.prompt,
      response: `Contribution level: ${contributionSteps[contributionIndex].title} - ${contributionSteps[contributionIndex].detail}.`,
      supportingEvidence: splitList(contributionNote)
    }
  ];
}

function promptFor(id: PositioningEvidenceResponse["topic"]) {
  return (
    positioningPrompts.find((prompt) => prompt.id === id) ??
    positioningPrompts[0]
  );
}

function indexFromText(text: string, fallback: number) {
  const spectrumIndex = spectrumLabels.findIndex((label) =>
    text.toLowerCase().includes(label.toLowerCase())
  );
  if (spectrumIndex >= 0) {
    return spectrumIndex;
  }
  const contributionIndex = contributionSteps.findIndex((step) =>
    text.toLowerCase().includes(step.title.toLowerCase())
  );
  return contributionIndex >= 0 ? contributionIndex : fallback;
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
