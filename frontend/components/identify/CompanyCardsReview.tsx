"use client";

import {
  companyCardContentStatus,
  companyCardDefinitions,
  companyCardDeckVersion,
  type CompanyCardDefinition,
  type CompanyCardTone
} from "@/data/company-cards";
import {
  getCompanyCards,
  saveCompanyCards
} from "@/lib/company-cards";
import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type CompanyCardsReviewProps = {
  assessmentId: string;
};

const toneClasses: Record<CompanyCardTone, string> = {
  violet: "border-purpos-line bg-purpos-lilac text-purpos-violet",
  blue: "border-sky-200 bg-sky-50 text-sky-800",
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  rose: "border-rose-200 bg-rose-50 text-rose-800",
  slate: "border-slate-200 bg-slate-100 text-slate-700"
};

export function CompanyCardsReview({ assessmentId }: CompanyCardsReviewProps) {
  const [currentCardIds, setCurrentCardIds] = useState<string[]>([]);
  const [desiredCardIds, setDesiredCardIds] = useState<string[]>([]);
  const [explanation, setExplanation] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [hasSavedSelections, setHasSavedSelections] = useState(false);

  useEffect(() => {
    let isMounted = true;

    getCompanyCards(assessmentId)
      .then((payload) => {
        if (isMounted) {
          const selections = payload.evidence?.selections ?? [];
          setCurrentCardIds(
            selections
              .filter((selection) => selection.state === "current")
              .map((selection) => selection.cardId)
          );
          setDesiredCardIds(
            selections
              .filter((selection) => selection.state === "desired")
              .map((selection) => selection.cardId)
          );
          setExplanation(payload.evidence?.explanation ?? "");
          setStatus(payload.message);
          setHasSavedSelections(Boolean(payload.evidence));
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load Company Cards.");
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

  useEffect(() => {
    let isMounted = true;

    getIdentifyBoardState(assessmentId)
      .then((payload) => {
        if (isMounted) {
          setConfidence(payload.confidence.overall);
          setCoverage(payload.playbookCoverage.slice(0, 6));
        }
      })
      .catch(() => {
        if (isMounted) {
          setConfidence(0);
          setCoverage([]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [assessmentId, status]);

  const localProgressLabel = useMemo(
    () => `${currentCardIds.length} today / ${desiredCardIds.length} future`,
    [currentCardIds.length, desiredCardIds.length]
  );

  function toggleCard(cardId: string, state: "current" | "desired") {
    const setter = state === "current" ? setCurrentCardIds : setDesiredCardIds;
    setter((selectedIds) =>
      selectedIds.includes(cardId)
        ? selectedIds.filter((selectedId) => selectedId !== cardId)
        : [...selectedIds, cardId]
    );
    setStatus(null);
    setError(null);
    setHasSavedSelections(false);
  }

  async function handleSave() {
    if (currentCardIds.length === 0 || desiredCardIds.length === 0) {
      setError("Select at least one Today card and one Future card.");
      setStatus(null);
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveCompanyCards({
        sessionId: assessmentId,
        currentCardIds,
        desiredCardIds,
        explanation: explanation.trim() || null
      });
      setStatus(payload.message);
      setHasSavedSelections(Boolean(payload.evidence));
    } catch {
      setError("I couldn't save Company Cards.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f2f2f4] text-[#292735]">
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
          <div className="hidden items-center gap-4 text-sm sm:flex">
            <span className="font-semibold tracking-[0.18em] text-slate-500">
              IDENTIFY
            </span>
            <span className="text-slate-400">01 Discover</span>
            <span className="font-semibold text-[#6f50b5]">02 Listen</span>
            <span className="text-slate-400">03 Understand</span>
            <span className="rounded-full border border-slate-200 px-3 py-1 font-semibold">
              <span className="mr-2 text-[#6f50b5]">●</span>
              Confidence {confidence}%
            </span>
          </div>
          <Link
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-[#292735] outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
            href={`/assessments/${assessmentId}/identify`}
          >
            Board
          </Link>
        </nav>
      </header>

      <main className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,1fr)_330px]">
        <section className="px-6 py-8 sm:px-10">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
                02 Listen - Company Cards
              </p>
              <h1 className="mt-3 text-3xl font-bold tracking-normal">
                If your company were one of these, which would it be?
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Pick what feels like today and tomorrow. The explanation turns
                the metaphor into evidence.
              </p>
            </div>
            <div className="inline-flex rounded-md border border-slate-200 bg-white p-1 text-sm font-bold shadow-sm">
              <span className="rounded bg-[#6f50b5] px-4 py-2 text-white">
                Today · {currentCardIds.length}
              </span>
              <span className="px-4 py-2 text-slate-600">
                Tomorrow · {desiredCardIds.length}
              </span>
            </div>
          </div>

          <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {isLoading ? (
                  <p className="text-sm text-slate-500">Loading Company Cards...</p>
                ) : (
                  companyCardDefinitions.map((card) => (
                    <CompanyCard
                      card={card}
                      isCurrent={currentCardIds.includes(card.id)}
                      isDesired={desiredCardIds.includes(card.id)}
                      key={card.id}
                      onToggle={toggleCard}
                    />
                  ))
                )}
              </div>
            </section>

            <aside className="grid gap-4">
              <section className="rounded-md border border-[#c9b9ef] bg-[#eee6fb] p-5">
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
                  One question per pick
                </p>
                <h2 className="mt-3 text-lg font-bold">
                  Why these cards? What do they do that your organisation does?
                </h2>
                <label className="mt-4 grid gap-2 text-sm font-bold">
                  Explanation
                  <textarea
                    className="min-h-28 resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium outline-none transition focus:border-[#6f50b5] focus:ring-2 focus:ring-[#6f50b5]/20"
                    onChange={(event) => {
                      setExplanation(event.target.value);
                      setStatus(null);
                      setHasSavedSelections(false);
                    }}
                    placeholder="We don't chase people. We stay steady and do the right thing..."
                    value={explanation}
                  />
                </label>
              </section>

              <section className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
                  Rate a few qualities
                </p>
                <div className="mt-4 grid gap-3">
                  {["Craftsmanship", "Speed", "Local roots", "Scale"].map(
                    (quality, index) => (
                      <div
                        className="flex items-center justify-between gap-3 text-sm"
                        key={quality}
                      >
                        <span>{quality}</span>
                        <span className="inline-flex overflow-hidden rounded-md border border-slate-200">
                          {["+", "=", "-"].map((mark, markIndex) => (
                            <span
                              className={`grid size-8 place-items-center ${
                                markIndex === index % 3
                                  ? "bg-[#292735] text-white"
                                  : "bg-white text-slate-500"
                              }`}
                              key={mark}
                            >
                              {mark}
                            </span>
                          ))}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </section>

              <button
                className="inline-flex min-h-11 w-full items-center justify-center rounded-md bg-[#6f50b5] px-5 text-sm font-bold text-white shadow-sm outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                disabled={isSaving || isLoading}
                data-stage-mutation
                onClick={handleSave}
                type="button"
              >
                {isSaving ? "Saving..." : "Save selections"}
              </button>

              {hasSavedSelections ? (
                <Link
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-slate-300 bg-white px-5 text-sm font-bold text-[#292735] outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                  href={`/assessments/${assessmentId}/identify/listen-summary`}
                >
                  Continue to Listen Summary
                </Link>
              ) : (
                <button
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-slate-200 bg-slate-100 px-5 text-sm font-bold text-slate-500"
                  disabled
                  type="button"
                >
                  Save to unlock Listen Summary
                </button>
              )}

              {error ? (
                <p className="text-sm font-medium text-red-700" role="alert">
                  {error}
                </p>
              ) : null}
              {status ? (
                <p className="text-sm font-medium text-[#6f50b5]">{status}</p>
              ) : null}
              <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                {companyCardContentStatus}
              </p>
            </aside>
          </div>
        </section>

        <aside className="border-l border-slate-200 bg-white px-6 py-8">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
            Confidence scorecard
          </p>
          <div className="mt-4 flex items-end gap-3">
            <p className="text-5xl font-bold leading-none">{confidence}%</p>
            <p className="pb-1 text-sm leading-4 text-slate-600">
              confident
              <br />
              across {coverage.length} areas
            </p>
          </div>
          <div className="mt-5 h-1.5 rounded-full bg-slate-200">
            <div
              className="h-1.5 rounded-full bg-[#6f50b5]"
              style={{ width: `${confidence}%` }}
            />
          </div>
          <p className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm font-semibold">
            {localProgressLabel} - deck {companyCardDeckVersion}
          </p>
          <div className="mt-6 grid gap-4">
            {coverage.map((item) => (
              <div key={item.areaId}>
                <div className="flex justify-between gap-3 text-sm">
                  <span>{item.label}</span>
                  <span className="text-xs text-[#6f50b5]">{item.status}</span>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-slate-200">
                  <div
                    className="h-1.5 rounded-full bg-[#6f50b5]"
                    style={{
                      width:
                        item.status === "sufficient"
                          ? "80%"
                          : item.status === "partial"
                            ? "45%"
                            : "10%"
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </aside>
      </main>
    </div>
  );
}

function CompanyCard({
  card,
  isCurrent,
  isDesired,
  onToggle
}: {
  card: CompanyCardDefinition;
  isCurrent: boolean;
  isDesired: boolean;
  onToggle: (cardId: string, state: "current" | "desired") => void;
}) {
  return (
    <article className="flex min-h-[220px] flex-col">
      <div
        className={`relative grid aspect-[4/2.8] place-items-center rounded-md border px-4 text-center ${
          toneClasses[card.tone]
        }`}
      >
        {isCurrent || isDesired ? (
          <span className="absolute right-2 top-2 grid size-6 place-items-center rounded-full bg-[#6f50b5] text-xs text-white">
            ✓
          </span>
        ) : null}
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em]">
            {card.quality}
          </p>
          <h3 className="mt-2 text-base font-bold text-purpos-ink">
            {card.title}
          </h3>
        </div>
      </div>
      <p className="mt-3 text-center text-sm font-bold leading-5 text-[#6f50b5]">
        {card.title}
      </p>
      <p className="mt-2 text-sm leading-5 text-slate-600">{card.cue}</p>
      <div className="mt-auto grid grid-cols-2 gap-2 pt-4">
        <button
          aria-pressed={isCurrent}
          className={`min-h-10 rounded-md border px-3 text-sm font-semibold outline-none transition focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2 ${
            isCurrent
              ? "border-[#6f50b5] bg-[#6f50b5] text-white"
              : "border-slate-300 bg-white text-[#292735] hover:border-[#6f50b5]"
          }`}
          onClick={() => onToggle(card.id, "current")}
          type="button"
        >
          Today
        </button>
        <button
          aria-pressed={isDesired}
          className={`min-h-10 rounded-md border px-3 text-sm font-semibold outline-none transition focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2 ${
            isDesired
              ? "border-[#6f50b5] bg-[#6f50b5] text-white"
              : "border-slate-300 bg-white text-[#292735] hover:border-[#6f50b5]"
          }`}
          onClick={() => onToggle(card.id, "desired")}
          type="button"
        >
          Future
        </button>
      </div>
    </article>
  );
}
