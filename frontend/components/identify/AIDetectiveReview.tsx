"use client";

import {
  aiDetectiveClassificationLabels,
  collectAIDetectiveFindings,
  getAIDetective,
  type AIDetectiveClassification,
  type AIDetectiveProgress,
  type ResearchFinding,
  researchSourceTypeLabels,
  saveAIDetectiveFindings
} from "@/lib/ai-detective";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type AIDetectiveReviewProps = {
  assessmentId: string;
};

const classifications: AIDetectiveClassification[] = [
  "correct",
  "wrong",
  "interesting",
  "investigate"
];

const classificationStyles: Record<
  AIDetectiveClassification,
  {
    panel: string;
    button: string;
    ring: string;
  }
> = {
  correct: {
    panel: "border-[#45a66f] bg-[#e4f3e7]",
    button: "border-[#45a66f] bg-[#45a66f] text-white",
    ring: "ring-[#45a66f]"
  },
  wrong: {
    panel: "border-[#cb5658] bg-[#f8e2e3]",
    button: "border-[#cb5658] bg-[#cb5658] text-white",
    ring: "ring-[#cb5658]"
  },
  interesting: {
    panel: "border-[#cf589a] bg-[#f9e2ef]",
    button: "border-[#cf589a] bg-[#cf589a] text-white",
    ring: "ring-[#cf589a]"
  },
  investigate: {
    panel: "border-[#5c8fd9] bg-[#e3eefb]",
    button: "border-[#5c8fd9] bg-[#5c8fd9] text-white",
    ring: "ring-[#5c8fd9]"
  }
};

export function AIDetectiveReview({ assessmentId }: AIDetectiveReviewProps) {
  const [findings, setFindings] = useState<ResearchFinding[]>([]);
  const [progress, setProgress] = useState<AIDetectiveProgress | null>(null);
  const [researchStatus, setResearchStatus] = useState("idle");
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCollecting, setIsCollecting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    getAIDetective(assessmentId)
      .then((payload) => {
        if (isMounted) {
          setFindings(payload.findings);
          setProgress(payload.progress);
          setResearchStatus(payload.research_status);
          setStatus(payload.message);
          setActiveFindingId(payload.findings[0]?.id ?? null);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load AI Detective.");
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

  const groupedFindings = useMemo(
    () =>
      classifications.reduce<Record<AIDetectiveClassification, ResearchFinding[]>>(
        (groups, classification) => {
          groups[classification] = findings.filter(
            (finding) => finding.classification === classification
          );
          return groups;
        },
        {
          correct: [],
          wrong: [],
          interesting: [],
          investigate: []
        }
      ),
    [findings]
  );

  const activeFinding =
    findings.find((finding) => finding.id === activeFindingId) ??
    findings[0] ??
    null;

  async function handleCollect() {
    setIsCollecting(true);
    setResearchStatus("collecting");
    setError(null);
    setStatus(null);

    try {
      const payload = await collectAIDetectiveFindings(assessmentId);
      setFindings(payload.findings);
      setProgress(payload.progress);
      setResearchStatus(payload.research_status);
      setStatus(payload.message);
      setActiveFindingId(payload.findings[0]?.id ?? null);
    } catch {
      setResearchStatus("error");
      setError("I couldn't collect AI Detective findings.");
    } finally {
      setIsCollecting(false);
    }
  }

  function updateFinding(
    findingId: string,
    updates: Partial<Pick<ResearchFinding, "classification" | "reviewNote">>
  ) {
    setFindings((current) =>
      current.map((finding) =>
        finding.id === findingId ? { ...finding, ...updates } : finding
      )
    );
    setStatus(null);
  }

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveAIDetectiveFindings({
        sessionId: assessmentId,
        findings
      });
      setFindings(payload.findings);
      setProgress(payload.progress);
      setResearchStatus(payload.research_status);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save the AI Detective review.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f0dd] text-[#2a2140]">
      <header className="border-b border-[#2a2140]/15 bg-[#fff9ea]">
        <nav className="flex min-h-16 items-center justify-between gap-4 px-5 sm:px-8">
          <Link
            className="flex items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#7256b8] focus-visible:ring-offset-2"
            href={`/assessments/${assessmentId}/identify`}
          >
            <span className="grid size-8 place-items-center rounded-md bg-[#7256b8] text-sm font-bold text-white">
              P
            </span>
            <span className="text-base font-bold">PurpOS</span>
          </Link>
          <div className="flex items-center gap-3">
            <button
              className="inline-flex min-h-10 items-center justify-center rounded-md bg-[#7256b8] px-4 text-sm font-semibold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-[#7256b8] focus-visible:ring-offset-2"
              disabled={isCollecting || isLoading}
              data-stage-mutation
              onClick={handleCollect}
              type="button"
            >
              {isCollecting ? "Collecting..." : "Collect"}
            </button>
            <button
              className="inline-flex min-h-10 items-center justify-center rounded-md border border-[#2a2140]/20 bg-white px-4 text-sm font-semibold text-[#2a2140] outline-none transition hover:border-[#7256b8] hover:text-[#7256b8] disabled:cursor-not-allowed disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-[#7256b8] focus-visible:ring-offset-2"
              disabled={isSaving || isLoading}
              data-stage-mutation
              onClick={handleSave}
              type="button"
            >
              {isSaving ? "Saving..." : "Save"}
            </button>
            <Link
              className="rounded-md border border-[#2a2140]/20 bg-white px-4 py-2 text-sm font-semibold text-[#2a2140] outline-none transition hover:border-[#7256b8] hover:text-[#7256b8] focus-visible:ring-2 focus-visible:ring-[#7256b8] focus-visible:ring-offset-2"
              href={`/assessments/${assessmentId}/identify`}
            >
              Board
            </Link>
          </div>
        </nav>
      </header>

      <main className="grid min-h-[calc(100vh-4rem)] grid-rows-[auto_minmax(0,1fr)]">
        <section className="grid gap-3 px-5 py-5 sm:px-8 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
              AI Detective
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-normal sm:text-4xl">
              Sort what the detective found.
            </h1>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="rounded-md border border-[#2a2140]/15 bg-white px-3 py-2 font-semibold">
              {isCollecting ? "Collecting" : researchStatusLabel(researchStatus)}
            </span>
            <span className="rounded-md border border-[#2a2140]/15 bg-white px-3 py-2 font-semibold">
              {progress?.label ?? "Loading AI Detective..."}
            </span>
          </div>
        </section>

        <section className="grid gap-4 px-5 pb-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="grid min-h-[650px] gap-3 md:grid-cols-2">
            {classifications.map((classification) => (
              <ClassificationPanel
                activeFindingId={activeFinding?.id ?? null}
                classification={classification}
                findings={groupedFindings[classification]}
                key={classification}
                onPick={setActiveFindingId}
              />
            ))}
          </div>

          <aside className="rounded-lg border border-[#2a2140]/20 bg-[#fff9ea] p-4 shadow-sm">
            {error ? (
              <p className="mb-3 text-sm font-medium text-red-700" role="alert">
                {error}
              </p>
            ) : null}
            {status ? (
              <p className="mb-3 text-sm font-medium text-[#7256b8]">
                {status}
              </p>
            ) : null}

            {isLoading ? (
              <p className="text-sm text-slate-500">Loading AI Detective...</p>
            ) : activeFinding ? (
              <ActiveFindingCard
                finding={activeFinding}
                onClassify={(classification) =>
                  updateFinding(activeFinding.id, { classification })
                }
                onNote={(reviewNote) =>
                  updateFinding(activeFinding.id, {
                    reviewNote: reviewNote.trim() ? reviewNote : null
                  })
                }
              />
            ) : (
              <div className="grid h-full min-h-[360px] place-items-center rounded-md border border-dashed border-[#2a2140]/20 bg-white/70 p-6 text-center">
                <p className="max-w-xs text-sm leading-6 text-slate-600">
                  Collect findings after SME input, uploaded evidence or
                  configured research sources are available.
                </p>
              </div>
            )}
          </aside>
        </section>
      </main>
    </div>
  );
}

function ClassificationPanel({
  activeFindingId,
  classification,
  findings,
  onPick
}: {
  activeFindingId: string | null;
  classification: AIDetectiveClassification;
  findings: ResearchFinding[];
  onPick: (findingId: string) => void;
}) {
  const styles = classificationStyles[classification];

  return (
    <section className={`rounded-lg border-2 p-4 ${styles.panel}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-2xl font-bold tracking-normal">
          {aiDetectiveClassificationLabels[classification]}
        </h2>
        <span className="rounded-full bg-white/80 px-3 py-1 text-sm font-bold">
          {findings.length}
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {findings.length === 0 ? (
          <p className="rounded-md border border-dashed border-[#2a2140]/20 bg-white/60 p-4 text-sm text-[#2a2140]/70">
            No findings here yet.
          </p>
        ) : (
          findings.map((finding) => (
            <button
              className={`rounded-md border border-[#2a2140]/15 bg-white p-3 text-left shadow-sm outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 ${
                activeFindingId === finding.id ? `ring-2 ${styles.ring}` : ""
              }`}
              key={finding.id}
              onClick={() => onPick(finding.id)}
              type="button"
            >
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#7256b8]">
                {researchSourceTypeLabels[finding.sourceType]}
              </p>
              <h3 className="mt-1 text-sm font-bold">{finding.topic}</h3>
              <p className="mt-2 line-clamp-3 text-sm leading-5 text-slate-700">
                {finding.summary}
              </p>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function ActiveFindingCard({
  finding,
  onClassify,
  onNote
}: {
  finding: ResearchFinding;
  onClassify: (classification: AIDetectiveClassification) => void;
  onNote: (reviewNote: string) => void;
}) {
  return (
    <article>
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
        Review finding
      </p>
      <h2 className="mt-2 text-2xl font-bold tracking-normal">
        {finding.topic}
      </h2>
      <p className="mt-4 text-sm leading-6 text-slate-700">
        {finding.summary}
      </p>

      <dl className="mt-5 grid gap-3 text-sm">
        <DetectiveDetail label="Source" value={finding.sourceLabel} />
        <DetectiveDetail
          label="Reference"
          value={finding.sourceReference ?? "No reference attached"}
        />
      </dl>

      <div className="mt-6 grid grid-cols-2 gap-2">
        {classifications.map((classification) => (
          <button
            className={`min-h-11 rounded-md border px-3 text-sm font-bold outline-none transition focus-visible:ring-2 focus-visible:ring-offset-2 ${
              finding.classification === classification
                ? classificationStyles[classification].button
                : "border-[#2a2140]/15 bg-white text-[#2a2140] hover:border-[#7256b8]"
            }`}
            key={classification}
            onClick={() => onClassify(classification)}
            type="button"
          >
            {aiDetectiveClassificationLabels[classification]}
          </button>
        ))}
      </div>

      <label className="mt-6 block text-sm font-bold" htmlFor="review-note">
        Review note
      </label>
      <textarea
        className="mt-2 min-h-28 w-full resize-y rounded-md border border-[#2a2140]/20 bg-white p-3 text-sm leading-6 outline-none transition focus:border-[#7256b8] focus:ring-2 focus:ring-[#7256b8]/20"
        defaultValue={finding.reviewNote ?? ""}
        id="review-note"
        key={finding.id}
        onBlur={(event) => onNote(event.currentTarget.value)}
        placeholder="Add a correction, follow-up, or reason this matters."
      />
    </article>
  );
}

function DetectiveDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 leading-6 text-slate-700">{value}</dd>
    </div>
  );
}

function researchStatusLabel(status: string) {
  if (status === "connected") {
    return "Connected";
  }
  if (status === "limited") {
    return "Limited";
  }
  if (status === "unavailable") {
    return "Unavailable";
  }
  if (status === "not-configured") {
    return "Not configured";
  }
  if (status === "retrieved") {
    return "Retrieved";
  }
  if (status === "error") {
    return "Error";
  }
  if (status === "collecting") {
    return "Collecting";
  }
  return "Idle";
}
