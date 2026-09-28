"use client";

import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import {
  getPerceptionGaps,
  reviewPerceptionGap,
  savePerceptionGaps,
  type EvidenceReference,
  type PerceptionGap,
  type PerceptionGapResolution
} from "@/lib/perception-gaps";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { UnderstandShell } from "./UnderstandShell";

type PerceptionGapsReviewProps = {
  assessmentId: string;
};

type FormState = {
  topic: string;
  perspectiveA: string;
  perspectiveB: string;
  difference: string;
  evidenceAId: string;
  evidenceBId: string;
};

const emptyForm: FormState = {
  topic: "",
  perspectiveA: "",
  perspectiveB: "",
  difference: "",
  evidenceAId: "",
  evidenceBId: ""
};

export function PerceptionGapsReview({ assessmentId }: PerceptionGapsReviewProps) {
  const [activityStatus, setActivityStatus] = useState<"locked" | "available">(
    "locked"
  );
  const [dependencyMessage, setDependencyMessage] = useState<string | null>(null);
  const [evidenceReferences, setEvidenceReferences] = useState<EvidenceReference[]>(
    []
  );
  const [suggestedGaps, setSuggestedGaps] = useState<PerceptionGap[]>([]);
  const [gaps, setGaps] = useState<PerceptionGap[]>([]);
  const [activeGapId, setActiveGapId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [reviewNote, setReviewNote] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([
      getPerceptionGaps(assessmentId),
      getIdentifyBoardState(assessmentId)
    ])
      .then(([gapResult, boardResult]) => {
        if (!isMounted) {
          return;
        }

        if (gapResult.status === "fulfilled") {
          const gapPayload = gapResult.value;
          setActivityStatus(gapPayload.activity_status);
          setDependencyMessage(gapPayload.dependency_message);
          setEvidenceReferences(gapPayload.evidenceReferences);
          setSuggestedGaps(gapPayload.suggestedGaps);
          setGaps(gapPayload.gaps);
          setActiveGapId(
            gapPayload.gaps[0]?.id ?? gapPayload.suggestedGaps[0]?.id ?? null
          );
          setForm((current) => ({
            ...current,
            evidenceAId: gapPayload.evidenceReferences[0]?.id ?? "",
            evidenceBId: gapPayload.evidenceReferences[1]?.id ?? ""
          }));
          setStatus(gapPayload.message);
          setLoadError(null);
          setError(null);
        } else {
          setLoadError("I couldn't load Perception Gaps.");
        }

        if (boardResult.status === "fulfilled") {
          setConfidence(boardResult.value.confidence.overall);
          setCoverage(boardResult.value.playbookCoverage.slice(0, 6));
          setProgressError(null);
        } else {
          setProgressError("I couldn't load Identify progress.");
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

  const evidenceById = useMemo(
    () => new Map(evidenceReferences.map((reference) => [reference.id, reference])),
    [evidenceReferences]
  );
  const allGaps = [...gaps, ...suggestedGaps];
  const activeGap =
    allGaps.find((gap) => gap.id === activeGapId) ?? allGaps[0] ?? null;
  const activeReferences =
    activeGap?.supportingEvidenceIds.map((id) => evidenceById.get(id)) ?? [];

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const evidenceIds = Array.from(
      new Set([form.evidenceAId, form.evidenceBId].filter(Boolean))
    );
    if (evidenceIds.length < 2) {
      setError("Link each gap to at least two evidence sources.");
      return;
    }

    const gap: PerceptionGap = {
      id: crypto.randomUUID(),
      topic: form.topic.trim(),
      perspectiveA: form.perspectiveA.trim(),
      perspectiveB: form.perspectiveB.trim(),
      difference: form.difference.trim(),
      supportingEvidenceIds: evidenceIds,
      clarificationNeeded: true,
      resolution: "unresolved",
      resolutionNote: null
    };

    setGaps((current) => [...current, gap]);
    setActiveGapId(gap.id);
    setForm({
      ...emptyForm,
      evidenceAId: evidenceReferences[0]?.id ?? "",
      evidenceBId: evidenceReferences[1]?.id ?? ""
    });
    setStatus(null);
    setError(null);
  }

  async function handleSave(nextGaps = gaps) {
    if (nextGaps.length === 0) {
      setError("Add or accept a real evidence gap before saving.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await savePerceptionGaps({
        sessionId: assessmentId,
        gaps: nextGaps
      });
      setActivityStatus(payload.activity_status);
      setDependencyMessage(payload.dependency_message);
      setEvidenceReferences(payload.evidenceReferences);
      setSuggestedGaps(payload.suggestedGaps);
      setGaps(payload.gaps);
      setActiveGapId(payload.gaps[0]?.id ?? payload.suggestedGaps[0]?.id ?? null);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save Perception Gaps.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReview(resolution: PerceptionGapResolution) {
    if (!activeGap || !gaps.some((gap) => gap.id === activeGap.id)) {
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await reviewPerceptionGap({
        sessionId: assessmentId,
        gapId: activeGap.id,
        resolution,
        clarificationNeeded: resolution === "unresolved",
        resolutionNote: reviewNote.trim() || undefined
      });
      setGaps(payload.gaps);
      setActiveGapId(payload.gaps[0]?.id ?? null);
      setReviewNote("");
      setStatus(payload.message);
    } catch {
      setError("I couldn't update that perception gap.");
    } finally {
      setIsSaving(false);
    }
  }

  function acceptSuggestedGap(gap: PerceptionGap) {
    const nextGaps = [...gaps, gap];
    setGaps(nextGaps);
    setSuggestedGaps((current) => current.filter((item) => item.id !== gap.id));
    setActiveGapId(gap.id);
    void handleSave(nextGaps);
  }

  return (
    <UnderstandShell
      assessmentId={assessmentId}
      confidence={confidence}
      coverage={coverage}
    >
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-purpos-violet">
              03 Understand - Perception Gaps
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-normal">
              Two things you told me don&apos;t quite match.
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              I&apos;m not catching you out. I want to understand which one is
              real.
            </p>
          </div>
          <p className="text-sm font-semibold text-slate-500">
            Gap {activeGap ? 1 : 0} of {Math.max(gaps.length, suggestedGaps.length)}
          </p>
        </div>

        {progressError ? (
          <p className="mt-5 text-sm font-semibold text-red-700" role="alert">
            {progressError}
          </p>
        ) : null}

        {!loadError && dependencyMessage ? (
          <p className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            {dependencyMessage}
          </p>
        ) : null}

        <section className="mt-5 overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm">
          {isLoading ? (
            <p className="p-6 text-sm text-slate-600">Loading gaps...</p>
          ) : loadError ? (
            <p className="p-6 text-sm font-semibold text-red-700" role="alert">
              {loadError}
            </p>
          ) : activeGap ? (
            <div className="grid md:grid-cols-[minmax(0,1fr)_64px_minmax(0,1fr)]">
              <EvidencePane
                detail={activeReferences[0]?.detail}
                label={activeReferences[0]?.label}
                sourceType={activeReferences[0]?.sourceType}
                text={activeGap.perspectiveA}
              />
              <div className="grid place-items-center border-y border-slate-200 bg-slate-50 md:border-x md:border-y-0">
                <span className="grid size-10 place-items-center rounded-full border border-slate-200 bg-white text-xs font-bold">
                  vs
                </span>
              </div>
              <EvidencePane
                detail={activeReferences[1]?.detail}
                label={activeReferences[1]?.label}
                sourceType={activeReferences[1]?.sourceType}
                text={activeGap.perspectiveB}
              />
            </div>
          ) : (
            <p className="p-6 text-sm leading-6 text-slate-600">
              No evidence-backed contradiction is visible yet. Add more saved
              Discover, Listen or Understand evidence, or manually add a gap
              only when the source material points in different directions.
            </p>
          )}
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="rounded-md border border-[#c9b9ef] bg-purpos-lilac p-5">
            <h2 className="text-lg font-bold tracking-normal">
              Which is closer to the truth?
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {activeGap?.difference ??
                "Use actual evidence only; the screen stays quiet until there is something real to compare."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {(["confirmed", "corrected", "clarified"] as const).map(
                (resolution) => (
                  <button
                    className="rounded-md border border-purpos-violet bg-white px-4 py-2 text-sm font-bold text-purpos-violet outline-none transition hover:bg-white/80 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                    disabled={
                      isSaving ||
                      Boolean(loadError) ||
                      !activeGap ||
                      !gaps.some((gap) => gap.id === activeGap.id)
                    }
                    key={resolution}
                    data-stage-mutation
                    onClick={() => handleReview(resolution)}
                    type="button"
                  >
                    {resolution}
                  </button>
                )
              )}
            </div>
            <input
              className="mt-4 min-h-11 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
              onChange={(event) => setReviewNote(event.target.value)}
              placeholder="Clarify what is going on here..."
              value={reviewNote}
            />
            {activeGap && suggestedGaps.some((gap) => gap.id === activeGap.id) ? (
              <button
                className="mt-4 inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                disabled={isSaving}
                data-stage-mutation
                onClick={() => acceptSuggestedGap(activeGap)}
                type="button"
              >
                Save this evidence gap
              </button>
            ) : null}
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
          </section>

          <aside>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
              Other gaps I&apos;m watching
            </p>
            <div className="mt-3 grid gap-3">
              {allGaps
                .filter((gap) => gap.id !== activeGap?.id)
                .slice(0, 4)
                .map((gap) => (
                  <button
                    className="rounded-md border border-slate-200 bg-white p-4 text-left text-sm font-semibold outline-none transition hover:border-purpos-violet focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                    key={gap.id}
                    onClick={() => setActiveGapId(gap.id)}
                    type="button"
                  >
                    <span className="mr-2 text-purpos-violet">●</span>
                    {gap.topic}: {gap.difference}
                  </button>
                ))}
              {!loadError && activityStatus === "locked" ? (
                <p className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm leading-6 text-slate-600">
                  Perception Gaps unlocks after two meaningful evidence sources.
                </p>
              ) : null}
            </div>
          </aside>
        </div>

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                Add a real gap manually
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                Use this only when the evidence references disagree.
              </p>
            </div>
            <Link
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
              href={`/assessments/${assessmentId}/identify/evidence-wall`}
            >
              Continue to Evidence Wall
            </Link>
          </div>
          <form className="mt-4 grid gap-3 lg:grid-cols-2" onSubmit={handleSubmit}>
            <TextField
              disabled={activityStatus === "locked" || Boolean(loadError)}
              label="Topic"
              onChange={(value) => setForm({ ...form, topic: value })}
              required
              value={form.topic}
            />
            <TextField
              disabled={activityStatus === "locked" || Boolean(loadError)}
              label="Difference"
              onChange={(value) => setForm({ ...form, difference: value })}
              required
              value={form.difference}
            />
            <TextField
              disabled={activityStatus === "locked" || Boolean(loadError)}
              label="Perspective A"
              onChange={(value) => setForm({ ...form, perspectiveA: value })}
              required
              value={form.perspectiveA}
            />
            <TextField
              disabled={activityStatus === "locked" || Boolean(loadError)}
              label="Perspective B"
              onChange={(value) => setForm({ ...form, perspectiveB: value })}
              required
              value={form.perspectiveB}
            />
            <EvidenceSelect
              disabled={activityStatus === "locked" || Boolean(loadError)}
              evidenceReferences={evidenceReferences}
              label="Evidence A"
              onChange={(value) => setForm({ ...form, evidenceAId: value })}
              value={form.evidenceAId}
            />
            <EvidenceSelect
              disabled={activityStatus === "locked" || Boolean(loadError)}
              evidenceReferences={evidenceReferences}
              label="Evidence B"
              onChange={(value) => setForm({ ...form, evidenceBId: value })}
              value={form.evidenceBId}
            />
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-md border border-slate-300 bg-white px-5 text-sm font-bold text-purpos-ink outline-none transition hover:border-purpos-violet hover:text-purpos-violet disabled:cursor-not-allowed disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2 lg:col-span-2"
              disabled={activityStatus === "locked" || Boolean(loadError) || isLoading}
              type="submit"
            >
              Add gap
            </button>
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2 lg:col-span-2"
              disabled={
                activityStatus === "locked" ||
                Boolean(loadError) ||
                isLoading ||
                isSaving
              }
              data-stage-mutation
              onClick={() => void handleSave()}
              type="button"
            >
              {isSaving ? "Saving..." : "Save gaps"}
            </button>
          </form>
        </section>
      </div>
    </UnderstandShell>
  );
}

function EvidencePane({
  detail,
  label,
  sourceType,
  text
}: {
  detail?: string | null;
  label?: string;
  sourceType?: string;
  text: string;
}) {
  return (
    <article className="p-6">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-purpos-violet">
        {sourceType ?? "Evidence"}
      </p>
      <h2 className="mt-4 text-xl font-bold leading-7 tracking-normal">
        &quot;{text}&quot;
      </h2>
      <p className="mt-4 text-sm leading-6 text-slate-600">
        {label}
        {detail ? ` - ${detail}` : ""}
      </p>
    </article>
  );
}

function EvidenceSelect({
  disabled,
  evidenceReferences,
  label,
  onChange,
  value
}: {
  disabled: boolean;
  evidenceReferences: EvidenceReference[];
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-purpos-ink">
      {label}
      <select
        className="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-sm outline-none transition disabled:bg-slate-100 focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        required
        value={value}
      >
        {evidenceReferences.map((reference) => (
          <option key={reference.id} value={reference.id}>
            {reference.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({
  disabled,
  label,
  onChange,
  required = false,
  value
}: {
  disabled: boolean;
  label: string;
  onChange: (value: string) => void;
  required?: boolean;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-purpos-ink">
      {label}
      <input
        className="min-h-10 rounded-md border border-slate-300 px-3 text-sm outline-none transition disabled:bg-slate-100 focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        value={value}
      />
    </label>
  );
}
