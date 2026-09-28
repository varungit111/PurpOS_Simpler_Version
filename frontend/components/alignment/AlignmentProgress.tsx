"use client";

import { getAlignment, getAlignmentContext, getAlignmentProgress, type AlignmentContext, type AlignmentState, type ProgressSnapshot } from "@/lib/alignment";
import { useEffect, useMemo, useState } from "react";
import { AlignmentError, AlignmentLoading, AlignmentShell } from "./AlignmentShell";

export function AlignmentProgress({ assessmentId }: { assessmentId: string }) {
  const [state, setState] = useState<AlignmentState | null>(null);
  const [context, setContext] = useState<AlignmentContext | null>(null);
  const [snapshots, setSnapshots] = useState<ProgressSnapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getAlignment(assessmentId), getAlignmentContext(assessmentId), getAlignmentProgress(assessmentId)])
      .then(([alignment, purpose, progress]) => {
        if (!active) return;
        setState(alignment); setContext(purpose); setSnapshots(progress);
      })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to load progress."); });
    return () => { active = false; };
  }, [assessmentId]);

  const actionNames = useMemo(() => new Map([
    ...(state?.priorityActions.map((item) => [item.id, item.action] as const) ?? []),
    ...(state?.adoptedActions.map((item) => [item.id, item.action] as const) ?? [])
  ]), [state]);
  const gapNames = useMemo(() => new Map(state?.gaps.map((item) => [item.id, item.title]) ?? []), [state]);
  const latest = snapshots?.at(-1);

  return (
    <AlignmentShell active="progress" assessmentId={assessmentId} organisationName={context?.organisation.companyName}>
      {error ? <AlignmentError message={error} /> : !state || !context || !snapshots ? <AlignmentLoading /> : (
        <>
          <header className="border-b border-[#dedede] pb-7">
            <p className="text-sm text-[#777]">Your business <span aria-hidden="true">/</span> Alignment <span aria-hidden="true">/</span> Progress</p>
            <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">Learning loop progress</h1>
            <p className="mt-3 max-w-3xl leading-7 text-[#696969]">Persisted snapshots show what was known at each recorded point in time. This page does not imply continuous monitoring.</p>
          </header>

          <section className="mt-6 grid gap-px border border-[#dedede] bg-[#dedede] sm:grid-cols-2 xl:grid-cols-4" aria-label="Current progress summary">
            <Summary label="Alignment score" value="Not calculated" />
            <Summary label="Adopted actions" value={String(state.adoptedActions.length)} />
            <Summary label="Recorded snapshots" value={String(snapshots.length)} />
            <Summary label="Latest snapshot" value={latest ? formatDate(latest.capturedAt) : "None yet"} />
          </section>

          {latest ? (
            <div className="mt-5 grid gap-5 xl:grid-cols-2">
              <ProgressGroup title="Alignment actions" description="Action state recorded in the latest snapshot.">
                <RecordList heading="Completed" ids={latest.completedActionIds} names={actionNames} empty="No completed actions recorded." />
                <RecordList heading="Outstanding" ids={latest.outstandingActionIds} names={actionNames} empty="No outstanding actions recorded." />
                <RecordList heading="Adopted commitments" ids={latest.adoptedActionIds} names={actionNames} empty="No adopted actions recorded in this snapshot." />
              </ProgressGroup>

              <ProgressGroup title="Gaps and learning" description="Resolved and unresolved gaps at this point in time.">
                <RecordList heading="Resolved" ids={latest.resolvedGapIds} names={gapNames} empty="No resolved gaps recorded." />
                <RecordList heading="Unresolved" ids={latest.unresolvedGapIds} names={gapNames} empty="No unresolved gaps recorded." />
                <div className="border-t border-[#e1e1e1] pt-5"><h3 className="text-sm font-semibold">Observations</h3>{latest.observations.length ? <ul className="mt-3 space-y-2 text-sm leading-6 text-[#626262]">{latest.observations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p className="mt-3 text-sm text-[#858585]">No qualitative observations recorded.</p>}</div>
              </ProgressGroup>
            </div>
          ) : (
            <section className="mt-5 border border-[#dedede] bg-white px-6 py-16 text-center"><h2 className="text-xl font-semibold">No progress snapshots yet</h2><p className="mx-auto mt-3 max-w-xl leading-7 text-[#707070]">Progress will appear here when persisted snapshots are available. No percentages or trend lines are inferred from missing data.</p></section>
          )}

          {snapshots.length > 1 ? (
            <section className="mt-5 border border-[#dedede] bg-white p-6" aria-labelledby="history-heading">
              <h2 className="text-xl font-semibold" id="history-heading">Snapshot history</h2>
              <ol className="mt-6 border-l border-[#bdbdbd] pl-6">
                {[...snapshots].reverse().map((snapshot) => <li className="relative pb-6 last:pb-0" key={snapshot.id}><span className="absolute -left-[29px] top-1 size-[9px] bg-[#1f63f3]" aria-hidden="true" /><p className="font-semibold">{formatDate(snapshot.capturedAt)}</p><p className="mt-1 text-sm text-[#707070]">{snapshot.observations[0] || "Structured progress snapshot recorded."}</p></li>)}
              </ol>
            </section>
          ) : null}

          <section className="mt-5 border-l-4 border-[#1f63f3] bg-[#eef4ff] px-5 py-4 text-sm leading-6 text-[#33435f]">
            Engagement, effectiveness, robustness, and progress percentages are not calculated because no approved methodology exists.
          </section>
        </>
      )}
    </AlignmentShell>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="min-h-32 bg-white p-5"><p className="text-sm text-[#777]">{label}</p><p className="mt-5 text-2xl font-semibold">{value}</p></div>;
}

function ProgressGroup({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="border border-[#dedede] bg-white p-6"><h2 className="text-xl font-semibold">{title}</h2><p className="mt-2 text-sm text-[#777]">{description}</p><div className="mt-6 space-y-5">{children}</div></section>;
}

function RecordList({ heading, ids, names, empty }: { heading: string; ids: string[]; names: Map<string, string>; empty: string }) {
  return <div className="border-t border-[#e1e1e1] pt-5"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{heading}</h3><span className="text-sm text-[#777]">{ids.length}</span></div>{ids.length ? <ul className="mt-3 space-y-2">{ids.map((id) => <li className="border-l-2 border-[#1f63f3] pl-3 text-sm leading-6 text-[#626262]" key={id}>{names.get(id) || "Recorded item"}</li>)}</ul> : <p className="mt-3 text-sm text-[#858585]">{empty}</p>}</div>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}
