"use client";

import {
  completeIdentify,
  getIdentifyCompletion,
  getIdentifyBrief,
  type IdentifyCompletionResponse,
  type IdentifyBriefEvidence,
  type IdentifyBriefResponse,
  type IdentifyBriefTheme
} from "@/lib/identify-brief";
import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import { generateDefine } from "@/lib/define";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  formatIdentifyBriefEvidenceClaim,
  formatIdentifyBriefQuestion
} from "./identify-brief-presentation";
import { UnderstandShell } from "./UnderstandShell";

type IdentifyBriefReviewProps = {
  assessmentId: string;
};

export function IdentifyBriefReview({ assessmentId }: IdentifyBriefReviewProps) {
  const router = useRouter();
  const [brief, setBrief] = useState<IdentifyBriefResponse | null>(null);
  const [completion, setCompletion] = useState<IdentifyCompletionResponse | null>(null);
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [coverageTotal, setCoverageTotal] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [isCompleting, setIsCompleting] = useState(false);
  const [isStartingDefine, setIsStartingDefine] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getIdentifyBrief(assessmentId),
      getIdentifyBoardState(assessmentId),
      getIdentifyCompletion(assessmentId)
    ])
      .then(([briefPayload, boardPayload, completionPayload]) => {
        if (isMounted) {
          setBrief(briefPayload);
          setConfidence(boardPayload.confidence.overall);
          setCoverage(boardPayload.playbookCoverage.slice(0, 6));
          setCoverageTotal(boardPayload.confidence.totalAreas);
          setCompletion(completionPayload);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load the Identify Brief.");
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

  const packText = useMemo(() => {
    if (!brief) {
      return "";
    }
    return [
      `Identify Brief: ${brief.organisationName}`,
      brief.website ? `Website: ${brief.website}` : null,
      "",
      brief.statement,
      "",
      "Themes",
      ...brief.themes.map(
        (theme) => `- ${theme.name}: ${theme.summary} (${theme.evidenceCount} evidence items)`
      ),
      "",
      "Strongest evidence",
      ...brief.strongestEvidence.map(
        (item) => `- [${item.sourceLabel}] ${formatIdentifyBriefEvidenceClaim(item)}`
      ),
      "",
      "Evidence to clarify in Define",
      ...brief.openQuestions.map(
        (question) =>
          `- [${question.source}] ${formatIdentifyBriefQuestion(question.question)}`
      ),
      "",
      `Coverage: ${brief.readiness.coveredAreaCount}/${brief.readiness.totalAreaCount} areas covered`,
      `Unresolved gaps: ${brief.unresolvedGapCount}`,
      `Handoff: ${brief.handoffLabel}`
    ]
      .filter((line): line is string => line !== null)
      .join("\n");
  }, [brief]);

  async function handleExportPack() {
    if (!brief) {
      return;
    }
    try {
      await navigator.clipboard.writeText(packText);
      setStatus("Identify handoff pack copied.");
    } catch {
      setStatus("Export pack ready. Select the brief text to copy it manually.");
    }
  }

  async function handleCompleteIdentify() {
    setIsCompleting(true);
    setError(null);
    try {
      const result = await completeIdentify(assessmentId);
      setCompletion(result);
      setStatus(
        result.readiness.status === "completed"
          ? "Identify is complete. Define is ready for the next implementation stage."
          : "Resolve the blocking items before completing Identify."
      );
    } catch {
      setError("I couldn't complete Identify.");
    } finally {
      setIsCompleting(false);
    }
  }

  async function handleStartDefine() {
    setIsStartingDefine(true);
    setError(null);
    try {
      await generateDefine(assessmentId);
      router.push(`/assessments/${assessmentId}/define`);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "I couldn't start Define. Your Identify work is still saved."
      );
    } finally {
      setIsStartingDefine(false);
    }
  }

  return (
    <UnderstandShell
      assessmentId={assessmentId}
      confidence={confidence}
      coverage={coverage}
      coverageTotal={coverageTotal}
      metricLabel="evidence-coverage"
    >
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-purpos-violet">
              {completion?.readiness.status === "completed"
                ? "Identify - Complete"
                : "Identify - Final review"}
              <span className="ml-2 rounded-full bg-purpos-lilac px-3 py-1 tracking-[0.14em]">
                {brief
                  ? `${brief.readiness.coveredAreaCount}/${brief.readiness.totalAreaCount} areas covered`
                  : "Loading"}
              </span>
            </p>
            <h1 className="mt-4 text-3xl font-bold tracking-normal">
              Your Identify Brief.
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Everything the Define agent needs to start shaping a purpose:
              evidence, not conclusions.
            </p>
          </div>
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-md border border-slate-300 bg-white px-5 text-sm font-bold text-purpos-ink outline-none transition hover:border-purpos-violet hover:text-purpos-violet disabled:cursor-not-allowed disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
            disabled={!brief || isLoading}
            onClick={handleExportPack}
            type="button"
          >
            Export pack
          </button>
        </div>

        {error ? (
          <p className="mt-5 text-sm font-semibold text-red-700" role="alert">
            {error}
          </p>
        ) : null}
        {status ? (
          <p className="mt-5 text-sm font-semibold text-purpos-violet">
            {status}
          </p>
        ) : null}

        <section className="mt-5 grid gap-4 lg:grid-cols-3">
          <BriefPanel title="Themes that emerged">
            {isLoading ? (
              <SkeletonLine count={4} />
            ) : brief?.themes.length ? (
              brief.themes.slice(0, 4).map((theme) => (
                <ThemeRow key={theme.id} theme={theme} />
              ))
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                Save an Evidence Wall theme to create the handoff themes.
              </p>
            )}
          </BriefPanel>

          <BriefPanel title="Strongest evidence">
            {isLoading ? (
              <SkeletonLine count={4} />
            ) : brief?.strongestEvidence.length ? (
              brief.strongestEvidence.slice(0, 5).map((item) => (
                <EvidenceRow key={item.id} item={item} />
              ))
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                Evidence from Identify activities will appear here once saved.
              </p>
            )}
          </BriefPanel>

          <BriefPanel title="Evidence to clarify in Define">
            {isLoading ? (
              <SkeletonLine count={4} />
            ) : brief?.openQuestions.length ? (
              <>
                <p className="text-sm leading-6 text-slate-600">
                  These evidence needs can carry into Define without blocking a completed
                  Identify handoff.
                </p>
                <ol className="grid gap-3">
                  {brief.openQuestions.slice(0, 5).map((question, index) => (
                    <li className="flex gap-3 text-sm leading-6" key={question.id}>
                      <span className="font-bold text-purpos-violet">
                        Q{index + 1}
                      </span>
                      <span>{formatIdentifyBriefQuestion(question.question)}</span>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                No unresolved gaps or uncovered areas are currently flagged.
              </p>
            )}
          </BriefPanel>
        </section>

        {brief ? (
          <section className="mt-5 rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
              Handoff evidence base
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <HandoffStat label="Discover" value={brief.sourceBreakdown.discover} />
              <HandoffStat label="Listen" value={brief.sourceBreakdown.listen} />
              <HandoffStat
                label="Understand"
                value={brief.sourceBreakdown.understand}
              />
              <HandoffStat label="Unresolved gaps" value={brief.unresolvedGapCount} />
            </div>
            {!brief.readiness.isReady ? (
              <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                Missing for handoff: {brief.readiness.missing.join(", ")}.
              </p>
            ) : null}
            {completion?.readiness.blockingIssues.length ? (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                <p className="font-bold">Resolve before completion</p>
                <ul className="mt-2 grid gap-1">
                  {completion.readiness.blockingIssues.map((issue) => (
                    <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="mt-5 rounded-md bg-purpos-violet p-6 text-white">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex gap-5">
              <span className="grid size-12 shrink-0 place-items-center rounded-md bg-white/15 text-2xl">
                -&gt;
              </span>
              <div>
                <h2 className="text-xl font-bold tracking-normal">
                  Hand this to the Define agent
                </h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-white/85">
                  A full evidence pack: themes, quotes, tensions and open
                  questions. This is not a purpose statement.
                </p>
              </div>
            </div>
            <button
              className="inline-flex min-h-12 items-center justify-center rounded-md bg-white px-6 text-sm font-bold text-purpos-violet outline-none transition hover:bg-white/90 disabled:cursor-not-allowed disabled:bg-white/40 disabled:text-white/70 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-purpos-violet"
              disabled={
                isCompleting ||
                isStartingDefine ||
                (completion?.readiness.status !== "completed" &&
                  !completion?.readiness.canComplete)
              }
              data-stage-mutation
              onClick={
                completion?.readiness.status === "completed"
                  ? handleStartDefine
                  : handleCompleteIdentify
              }
              type="button"
            >
              {completion?.readiness.status === "completed"
                ? isStartingDefine
                  ? "Shaping your proposal..."
                  : "Continue to Define"
                : isCompleting
                  ? "Completing Identify..."
                  : "Complete Identify"}
              <span className="ml-2">-&gt;</span>
            </button>
          </div>
        </section>

        <Link
          className="mt-5 inline-flex text-sm font-bold text-purpos-violet underline decoration-purpos-violet/30 underline-offset-4"
          href={`/assessments/${assessmentId}/identify`}
        >
          Return to Investigation Board
        </Link>
      </div>
    </UnderstandShell>
  );
}

function BriefPanel({
  children,
  title
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <article className="min-h-56 rounded-md border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
        {title}
      </p>
      <div className="mt-5 grid gap-4">{children}</div>
    </article>
  );
}

function ThemeRow({ theme }: { theme: IdentifyBriefTheme }) {
  return (
    <div className="border-l-4 border-purpos-violet/30 pl-4">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-bold">{theme.name}</span>
        {theme.isLead ? (
          <span className="text-xs font-bold uppercase text-purpos-violet">
            Lead
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-sm leading-6 text-slate-600">{theme.summary}</p>
    </div>
  );
}

function EvidenceRow({ item }: { item: IdentifyBriefEvidence }) {
  return (
    <div className="border-l-4 border-purpos-violet pl-4">
      <p className="text-sm leading-6 text-slate-700">
        {formatIdentifyBriefEvidenceClaim(item)}
      </p>
      <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
        {item.sourceLabel}
      </p>
    </div>
  );
}

function HandoffStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}

function SkeletonLine({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <span
          className="h-4 animate-pulse rounded-full bg-slate-200"
          key={index}
        />
      ))}
    </>
  );
}
