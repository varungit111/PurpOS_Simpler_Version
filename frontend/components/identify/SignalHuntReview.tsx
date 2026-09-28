"use client";

import {
  generateSignalHuntFindings,
  getSignalHunt,
  type PESTLEFinding,
  pestleCategoryLabels,
  saveSignalHuntFindings,
  type SignalHuntDecision,
  signalHuntDecisionLabels,
  type SignalHuntProgress
} from "@/lib/signal-hunt";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type SignalHuntReviewProps = {
  assessmentId: string;
};

const decisions: SignalHuntDecision[] = [
  "ignore",
  "watch",
  "opportunity",
  "threat"
];

const decisionStyles: Record<SignalHuntDecision, string> = {
  unplaced: "border-slate-300 bg-white text-slate-600",
  ignore: "border-[#b8b6aa] bg-[#efede0] text-[#4f4b3f]",
  watch: "border-[#5c8fd9] bg-[#dceaf9] text-[#224f88]",
  opportunity: "border-[#45a66f] bg-[#dcf1e2] text-[#276441]",
  threat: "border-[#cb5658] bg-[#f6dfe0] text-[#7d2f31]"
};

export function SignalHuntReview({ assessmentId }: SignalHuntReviewProps) {
  const [findings, setFindings] = useState<PESTLEFinding[]>([]);
  const [progress, setProgress] = useState<SignalHuntProgress | null>(null);
  const [aiStatus, setAiStatus] = useState("idle");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    getSignalHunt(assessmentId)
      .then((payload) => {
        if (isMounted) {
          setFindings(payload.findings);
          setProgress(payload.progress);
          setAiStatus(payload.ai_status);
          setStatus(payload.message);
          setSelectedId(payload.findings[0]?.id ?? null);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load Signal Hunt.");
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

  const selectedFinding =
    findings.find((finding) => finding.id === selectedId) ?? findings[0] ?? null;

  const placedCount = useMemo(
    () => findings.filter((finding) => finding.decision !== "unplaced").length,
    [findings]
  );

  const categorySummary = useMemo(() => {
    if (!progress || progress.categoriesCovered.length === 0) {
      return "No PESTLE categories represented yet";
    }

    return `${progress.categoriesCovered.length}/${progress.totalCategories} PESTLE categories`;
  }, [progress]);

  async function handleGenerate() {
    setIsGenerating(true);
    setAiStatus("ai-running");
    setError(null);
    setStatus(null);

    try {
      const payload = await generateSignalHuntFindings(assessmentId);
      setFindings(payload.findings);
      setProgress(payload.progress);
      setAiStatus(payload.ai_status);
      setStatus(payload.message);
      setSelectedId(payload.findings[0]?.id ?? null);
    } catch {
      setAiStatus("error");
      setError("I couldn't run the Signal Hunt analysis.");
    } finally {
      setIsGenerating(false);
    }
  }

  function updateFinding(
    findingId: string,
    updates: Partial<Pick<PESTLEFinding, "decision" | "impact" | "urgency">>
  ) {
    setFindings((current) =>
      current.map((finding) =>
        finding.id === findingId ? { ...finding, ...updates } : finding
      )
    );
    setStatus(null);
  }

  function placeFinding(finding: PESTLEFinding, decision: SignalHuntDecision) {
    updateFinding(finding.id, {
      decision,
      impact: finding.impact ?? defaultPlacement(decision).impact,
      urgency: finding.urgency ?? defaultPlacement(decision).urgency
    });
    setSelectedId(finding.id);
  }

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveSignalHuntFindings({
        sessionId: assessmentId,
        findings
      });
      setFindings(payload.findings);
      setProgress(payload.progress);
      setAiStatus(payload.ai_status);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save the Signal Hunt review.");
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
              disabled={isGenerating || isLoading}
              data-stage-mutation
              onClick={handleGenerate}
              type="button"
            >
              {isGenerating ? "Running..." : "Run analysis"}
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

      <main className="grid gap-5 px-5 py-6 sm:px-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section>
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
                Signal Hunt
              </p>
              <h1 className="mt-1 text-3xl font-bold tracking-normal sm:text-4xl">
                Plot the signals shaping the next three years.
              </h1>
            </div>
            <div className="flex flex-wrap gap-2 text-sm">
              <span className="rounded-md border border-[#2a2140]/15 bg-white px-3 py-2 font-semibold">
                {isGenerating ? "AI running" : aiStatusLabel(aiStatus)}
              </span>
              <span className="rounded-md border border-[#2a2140]/15 bg-white px-3 py-2 font-semibold">
                {placedCount}/{findings.length} placed
              </span>
              <span className="rounded-md border border-[#2a2140]/15 bg-white px-3 py-2 font-semibold">
                {categorySummary}
              </span>
            </div>
          </div>

          <div className="relative min-h-[620px] rounded-lg border-2 border-[#2a2140] bg-[#fff9ea] p-10 shadow-sm">
            <span className="absolute left-3 top-5 text-xs font-bold uppercase tracking-[0.16em] text-[#2a2140]/70 [writing-mode:vertical-rl]">
              Higher impact
            </span>
            <span className="absolute bottom-5 left-3 text-xs font-bold uppercase tracking-[0.16em] text-[#2a2140]/70 [writing-mode:vertical-rl]">
              Lower impact
            </span>
            <span className="absolute bottom-3 left-12 text-xs font-bold uppercase tracking-[0.16em] text-[#2a2140]/70">
              Now
            </span>
            <span className="absolute bottom-3 right-12 text-xs font-bold uppercase tracking-[0.16em] text-[#2a2140]/70">
              3 yrs
            </span>

            <div className="grid h-full min-h-[540px] grid-cols-2 grid-rows-2 border-2 border-[#2a2140]/80">
              <Quadrant label="Watch" tone="bg-[#dceaf9]" />
              <Quadrant label="Opportunity" tone="bg-[#dcf1e2]" />
              <Quadrant label="Ignore" tone="bg-[#efede0]" />
              <Quadrant label="Threat" tone="bg-[#f6dfe0]" />
            </div>

            <div className="absolute inset-10">
              {findings
                .filter((finding) => finding.decision !== "unplaced")
                .map((finding) => (
                  <button
                    className={`absolute max-w-[190px] -translate-x-1/2 -translate-y-1/2 rounded-md border px-3 py-2 text-left text-xs font-bold shadow-sm outline-none transition hover:z-20 hover:-translate-y-[55%] focus-visible:z-20 focus-visible:ring-2 focus-visible:ring-[#7256b8] ${
                      decisionStyles[finding.decision]
                    }`}
                    key={finding.id}
                    onClick={() => setSelectedId(finding.id)}
                    style={{
                      left: `${finding.urgency ?? 50}%`,
                      top: `${100 - (finding.impact ?? 50)}%`
                    }}
                    type="button"
                  >
                    {finding.signal}
                  </button>
                ))}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {decisions.map((decision) => (
              <span
                className={`rounded-full border px-3 py-1 text-xs font-bold ${decisionStyles[decision]}`}
                key={decision}
              >
                {signalHuntDecisionLabels[decision]}
              </span>
            ))}
          </div>

          <div className="mt-5 rounded-lg border border-[#2a2140]/15 bg-[#fff9ea] p-4">
            <p className="text-sm font-bold text-[#2a2140]">
              Signals waiting to be placed
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {findings.filter((finding) => finding.decision === "unplaced")
                .length === 0 ? (
                <p className="text-sm text-slate-600">
                  Every generated signal has a decision.
                </p>
              ) : (
                findings
                  .filter((finding) => finding.decision === "unplaced")
                  .map((finding) => (
                    <button
                      className="rounded-full border border-[#2a2140]/15 bg-white px-3 py-2 text-sm font-semibold outline-none transition hover:border-[#7256b8] hover:text-[#7256b8] focus-visible:ring-2 focus-visible:ring-[#7256b8]"
                      key={finding.id}
                      onClick={() => setSelectedId(finding.id)}
                      type="button"
                    >
                      {finding.signal}
                    </button>
                  ))
              )}
            </div>
          </div>
        </section>

        <aside className="rounded-lg border border-[#2a2140]/20 bg-[#fff9ea] p-4 shadow-sm">
          {error ? (
            <p className="mb-3 text-sm font-medium text-red-700" role="alert">
              {error}
            </p>
          ) : null}
          {status ? (
            <p className="mb-3 text-sm font-medium text-[#7256b8]">{status}</p>
          ) : null}

          {isLoading ? (
            <p className="text-sm text-slate-500">Loading Signal Hunt...</p>
          ) : selectedFinding ? (
            <SignalEditor
              finding={selectedFinding}
              onDecision={(decision) => placeFinding(selectedFinding, decision)}
              onImpact={(impact) => updateFinding(selectedFinding.id, { impact })}
              onUrgency={(urgency) =>
                updateFinding(selectedFinding.id, { urgency })
              }
            />
          ) : (
            <div className="grid min-h-[360px] place-items-center rounded-md border border-dashed border-[#2a2140]/20 bg-white/70 p-6 text-center">
              <p className="max-w-xs text-sm leading-6 text-slate-600">
                Run the analysis to generate signals for review.
              </p>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function Quadrant({ label, tone }: { label: string; tone: string }) {
  return (
    <div className={`relative border border-[#2a2140]/70 ${tone}`}>
      <span className="absolute left-4 top-4 text-xl font-bold text-[#2a2140]/55">
        {label}
      </span>
    </div>
  );
}

function SignalEditor({
  finding,
  onDecision,
  onImpact,
  onUrgency
}: {
  finding: PESTLEFinding;
  onDecision: (decision: SignalHuntDecision) => void;
  onImpact: (impact: number) => void;
  onUrgency: (urgency: number) => void;
}) {
  return (
    <article>
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
        {pestleCategoryLabels[finding.category]}
      </p>
      <h2 className="mt-2 text-2xl font-bold tracking-normal">
        {finding.signal}
      </h2>
      <p className="mt-4 text-sm leading-6 text-slate-700">
        {finding.description}
      </p>
      <p className="mt-3 text-sm leading-6 text-slate-700">
        {finding.whyItMatters}
      </p>

      <div className="mt-6 grid grid-cols-2 gap-2">
        {decisions.map((decision) => (
          <button
            className={`min-h-11 rounded-md border px-3 text-sm font-bold outline-none transition focus-visible:ring-2 focus-visible:ring-[#7256b8] focus-visible:ring-offset-2 ${
              finding.decision === decision
                ? decisionStyles[decision]
                : "border-[#2a2140]/15 bg-white text-[#2a2140] hover:border-[#7256b8]"
            }`}
            key={decision}
            onClick={() => onDecision(decision)}
            type="button"
          >
            {signalHuntDecisionLabels[decision]}
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-5">
        <LabeledRange
          label="Impact"
          onChange={onImpact}
          value={finding.impact ?? defaultPlacement(finding.decision).impact}
        />
        <LabeledRange
          label="Time horizon"
          onChange={onUrgency}
          value={finding.urgency ?? defaultPlacement(finding.decision).urgency}
        />
      </div>

      <dl className="mt-6 grid gap-3 text-sm">
        <SignalDetail label="Opportunity or risk" value={finding.opportunityOrRisk} />
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Evidence
          </dt>
          <dd className="mt-1 text-slate-700">
            {finding.evidenceSources.length === 0 ? (
              "No source attached"
            ) : (
              <ul className="grid gap-2">
                {finding.evidenceSources.map((source) => (
                  <li key={source.id ?? `${source.title}-${source.sourceType}`}>
                    <span className="font-medium">{source.title}</span>
                    <span className="text-slate-500"> / {source.sourceType}</span>
                    {source.summary ? (
                      <p className="mt-1 leading-5">{source.summary}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function LabeledRange({
  label,
  onChange,
  value
}: {
  label: string;
  onChange: (value: number) => void;
  value: number;
}) {
  return (
    <label className="grid gap-2 text-sm font-bold">
      <span className="flex items-center justify-between">
        {label}
        <span>{value}</span>
      </span>
      <input
        className="accent-[#7256b8]"
        max={100}
        min={0}
        onChange={(event) => onChange(Number(event.currentTarget.value))}
        type="range"
        value={value}
      />
    </label>
  );
}

function SignalDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 leading-6 text-slate-700">{value}</dd>
    </div>
  );
}

function defaultPlacement(decision: SignalHuntDecision) {
  if (decision === "watch") {
    return { impact: 78, urgency: 28 };
  }
  if (decision === "opportunity") {
    return { impact: 78, urgency: 72 };
  }
  if (decision === "threat") {
    return { impact: 30, urgency: 72 };
  }
  if (decision === "ignore") {
    return { impact: 30, urgency: 28 };
  }
  return { impact: 50, urgency: 50 };
}

function aiStatusLabel(status: string) {
  if (status === "connected") {
    return "Connected";
  }
  if (status === "unavailable") {
    return "Unavailable";
  }
  if (status === "error") {
    return "Error";
  }
  if (status === "ai-running") {
    return "AI running";
  }
  return "Idle";
}
