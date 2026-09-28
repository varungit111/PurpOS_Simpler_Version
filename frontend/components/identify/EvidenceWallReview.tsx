"use client";

import {
  getEvidenceWall,
  saveEvidenceWallThemes,
  type EvidenceWallCard,
  type EvidenceWallGroup
} from "@/lib/evidence-wall";
import { getIdentifyBoardState, type PlaybookCoverage } from "@/lib/identify-board";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { UnderstandShell, sourceStage } from "./UnderstandShell";

type EvidenceWallReviewProps = {
  assessmentId: string;
};

const cardTypeClasses: Record<EvidenceWallCard["cardType"], string> = {
  strength: "bg-purpos-violet",
  tension: "bg-purpos-ink",
  "touch-point": "bg-[#d98235]",
  fact: "bg-slate-400"
};

export function EvidenceWallReview({ assessmentId }: EvidenceWallReviewProps) {
  const [groups, setGroups] = useState<EvidenceWallGroup[]>([]);
  const [evidenceCount, setEvidenceCount] = useState(0);
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
  const [confidence, setConfidence] = useState(0);
  const [coverage, setCoverage] = useState<PlaybookCoverage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getEvidenceWall(assessmentId),
      getIdentifyBoardState(assessmentId)
    ])
      .then(([wallPayload, boardPayload]) => {
        if (isMounted) {
          setGroups(wallPayload.groups);
          setEvidenceCount(wallPayload.evidenceCount);
          setSelectedGroupIds(
            wallPayload.selectedThemes
              .map((theme) =>
                wallPayload.groups.find((group) => group.title === theme.name)?.id
              )
              .filter((groupId): groupId is string => Boolean(groupId))
          );
          setConfidence(boardPayload.confidence.overall);
          setCoverage(boardPayload.playbookCoverage.slice(0, 6));
          setStatus(wallPayload.message);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load the Evidence Wall.");
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

  const selectedTitle = useMemo(() => {
    const selected = groups.find((group) => selectedGroupIds.includes(group.id));
    return selected?.title ?? "the strongest evidence cluster";
  }, [groups, selectedGroupIds]);

  function toggleGroup(groupId: string) {
    setSelectedGroupIds((current) =>
      current.includes(groupId)
        ? current.filter((id) => id !== groupId)
        : [...current, groupId]
    );
    setStatus(null);
    setError(null);
  }

  async function handleSave() {
    if (selectedGroupIds.length === 0) {
      setError("Point to at least one evidence cluster before saving.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const payload = await saveEvidenceWallThemes({
        sessionId: assessmentId,
        selectedGroupIds
      });
      setGroups(payload.groups);
      setStatus(payload.message);
    } catch {
      setError("I couldn't save the Evidence Wall synthesis.");
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
          03 Understand - Evidence Wall
        </p>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-normal">
              The whole investigation, on one wall.
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {evidenceCount} pieces of evidence grouped by the existing
              20-question coverage framework.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-xs font-semibold text-slate-500">
            {(["strength", "tension", "touch-point", "fact"] as const).map(
              (type) => (
                <span className="inline-flex items-center gap-2" key={type}>
                  <span className={`size-2 ${cardTypeClasses[type]}`} />
                  {type}
                </span>
              )
            )}
          </div>
        </div>

        <section className="mt-5 grid gap-4 lg:grid-cols-2">
          {isLoading ? (
            <p className="rounded-md border border-slate-200 bg-white p-5 text-sm text-slate-600">
              Loading Evidence Wall...
            </p>
          ) : groups.length === 0 ? (
            <p className="rounded-md border border-dashed border-slate-300 bg-white p-5 text-sm leading-6 text-slate-600 lg:col-span-2">
              Complete Discover, Listen or Understand activities to collect
              evidence for the wall.
            </p>
          ) : (
            groups.slice(0, 8).map((group) => (
              <EvidenceGroup
                group={group}
                isSelected={selectedGroupIds.includes(group.id)}
                key={group.id}
                onToggle={toggleGroup}
              />
            ))
          )}
        </section>

        <section className="mt-5 rounded-md bg-purpos-ink p-5 text-white">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-bold tracking-normal">
                Which of these feels most fundamentally true about why this
                place matters?
              </h2>
              <p className="mt-1 text-sm leading-6 text-white/70">
                Save the Evidence Wall synthesis for the Investigation Board.
                The final Identify Brief waits for Phase 7.
              </p>
            </div>
            <button
              className="inline-flex min-h-11 items-center justify-center rounded-md bg-purpos-violet px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-500 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-purpos-ink"
              disabled={isSaving || isLoading || groups.length === 0}
              data-stage-mutation
              onClick={handleSave}
              type="button"
            >
              {isSaving ? "Saving..." : `Point to ${selectedTitle}`}
            </button>
          </div>
          {error ? (
            <p className="mt-3 text-sm font-semibold text-red-200" role="alert">
              {error}
            </p>
          ) : null}
          {status ? (
            <p className="mt-3 text-sm font-semibold text-white">{status}</p>
          ) : null}
          <Link
            className="mt-4 inline-flex text-sm font-semibold text-white underline decoration-white/40 underline-offset-4"
            href={`/assessments/${assessmentId}/identify`}
          >
            Return to Investigation Board
          </Link>
        </section>
      </div>
    </UnderstandShell>
  );
}

function EvidenceGroup({
  group,
  isSelected,
  onToggle
}: {
  group: EvidenceWallGroup;
  isSelected: boolean;
  onToggle: (groupId: string) => void;
}) {
  return (
    <article
      className={`rounded-md border bg-white p-5 ${
        isSelected
          ? "border-purpos-violet bg-purpos-lilac"
          : "border-dashed border-slate-300"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold tracking-normal text-purpos-ink">
            {group.title}
          </h2>
          <p className="mt-1 text-xs font-semibold text-slate-500">
            {group.evidenceCount} card{group.evidenceCount === 1 ? "" : "s"} -
            {group.status}
          </p>
        </div>
        <button
          aria-pressed={isSelected}
          className="grid size-8 shrink-0 place-items-center rounded-full border border-slate-300 bg-white text-sm font-bold text-purpos-violet outline-none transition hover:border-purpos-violet focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
          onClick={() => onToggle(group.id)}
          type="button"
        >
          {isSelected ? "✓" : "☆"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {group.cards.map((card) => (
          <span
            className="inline-flex max-w-full items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-5"
            key={card.id}
            title={card.claim}
          >
            <span className={`size-2 shrink-0 ${cardTypeClasses[card.cardType]}`} />
            <span className="truncate">
              {card.summary ?? card.claim}
            </span>
            <span className="shrink-0 text-xs text-slate-400">
              {sourceStage(card.sourceActivity)}
            </span>
          </span>
        ))}
      </div>
    </article>
  );
}
