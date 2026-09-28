"use client";

import {
  generateDiscoverSynthesis,
  getDiscoverSynthesis,
  saveDiscoverSynthesis,
  type DiscoverSynthesisProgress
} from "@/lib/discover-synthesis";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type DiscoverSynthesisReviewProps = {
  assessmentId: string;
};

export function DiscoverSynthesisReview({
  assessmentId
}: DiscoverSynthesisReviewProps) {
  const [statement, setStatement] = useState("");
  const [gaugeItems, setGaugeItems] = useState<string[]>([]);
  const [progress, setProgress] = useState<DiscoverSynthesisProgress | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    getDiscoverSynthesis(assessmentId)
      .then((payload) => {
        if (isMounted) {
          setStatement(payload.statement ?? "");
          setGaugeItems(payload.gauge_items);
          setProgress(payload.progress);
          setStatus(payload.message);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load Discover Synthesis.");
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

  const gaugePercent = useMemo(() => {
    if (!progress) {
      return 0;
    }
    return Math.min(100, progress.evidenceCount * 12);
  }, [progress]);

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await generateDiscoverSynthesis(assessmentId);
      setStatement(payload.statement ?? "");
      setGaugeItems(payload.gauge_items);
      setProgress(payload.progress);
      setStatus(payload.message);
    } catch {
      setError("I couldn't generate Discover Synthesis.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSave() {
    if (!statement.trim()) {
      setError("Add a synthesis statement before saving.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveDiscoverSynthesis({
        sessionId: assessmentId,
        statement: statement.trim()
      });
      setStatement(payload.statement ?? "");
      setGaugeItems(payload.gauge_items);
      setProgress(payload.progress);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save Discover Synthesis.");
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
              {isGenerating ? "Generating..." : "Generate"}
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

      <main className="grid min-h-[calc(100vh-4rem)] gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="flex min-h-[650px] flex-col rounded-lg border-2 border-[#2a2140] bg-[#fff9ea] p-6 shadow-sm">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
              Discover Synthesis
            </p>
            <h1 className="mt-2 max-w-4xl text-3xl font-bold leading-tight tracking-normal sm:text-5xl">
              {statement.trim()
                ? statement
                : "Review the Discover evidence, then generate a first synthesis."}
            </h1>
          </div>

          <label className="mt-8 block text-sm font-bold" htmlFor="statement">
            Synthesis statement
          </label>
          <textarea
            className="mt-2 min-h-52 w-full flex-1 resize-y rounded-md border border-[#2a2140]/20 bg-white p-4 text-lg leading-8 outline-none transition focus:border-[#7256b8] focus:ring-2 focus:ring-[#7256b8]/20"
            id="statement"
            onChange={(event) => setStatement(event.currentTarget.value)}
            placeholder="Generate from reviewed Discover evidence, or write a concise evidence-backed statement."
            value={statement}
          />

          {error ? (
            <p className="mt-4 text-sm font-medium text-red-700" role="alert">
              {error}
            </p>
          ) : null}
          {status ? (
            <p className="mt-4 text-sm font-medium text-[#7256b8]">{status}</p>
          ) : null}
        </section>

        <aside className="grid gap-4">
          <section className="rounded-lg border border-[#2a2140]/20 bg-[#fff9ea] p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
              Evidence rail
            </p>
            <div className="mt-5 flex items-center gap-4">
              <div className="h-44 w-4 rounded-full border border-[#2a2140]/20 bg-white p-1">
                <div
                  className="mt-auto rounded-full bg-[#7256b8]"
                  style={{ height: `${gaugePercent}%` }}
                />
              </div>
              <div>
                <p className="text-5xl font-bold tracking-normal">
                  {progress?.evidenceCount ?? 0}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-600">
                  {progress?.label ?? "Loading evidence..."}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-[#2a2140]/20 bg-[#fff9ea] p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7256b8]">
              Reviewed material
            </p>
            <div className="mt-4 grid gap-3">
              {isLoading ? (
                <p className="text-sm text-slate-500">
                  Loading Discover evidence...
                </p>
              ) : gaugeItems.length === 0 ? (
                <p className="text-sm leading-6 text-slate-600">
                  Save AI Detective classifications or Signal Hunt decisions to
                  create synthesis material.
                </p>
              ) : (
                gaugeItems.map((item, index) => (
                  <p
                    className="rounded-md border border-[#2a2140]/10 bg-white p-3 text-sm font-semibold leading-5 text-[#2a2140]"
                    key={`${item}-${index}`}
                  >
                    {item}
                  </p>
                ))
              )}
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}
