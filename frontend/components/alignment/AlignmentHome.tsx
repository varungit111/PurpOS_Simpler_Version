"use client";

import { getAlignment, getAlignmentContext, type AlignmentContext, type AlignmentState } from "@/lib/alignment";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlignmentError, AlignmentLoading, AlignmentShell } from "./AlignmentShell";

const findingLabels = {
  aligned: "Aligned",
  tension: "Tension",
  gap: "Gap to close",
  "insufficient-evidence": "Needs evidence"
};

const findingStyles = {
  aligned: "border-[#2d8a62] text-[#216b4c]",
  tension: "border-[#d78713] text-[#9a5d00]",
  gap: "border-[#c93838] text-[#9d2727]",
  "insufficient-evidence": "border-[#777] text-[#5f5f5f]"
};

export function AlignmentHome({ assessmentId }: { assessmentId: string }) {
  const [state, setState] = useState<AlignmentState | null>(null);
  const [context, setContext] = useState<AlignmentContext | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getAlignment(assessmentId), getAlignmentContext(assessmentId)])
      .then(([alignment, purpose]) => {
        if (!active) return;
        setState(alignment);
        setContext(purpose);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Unable to load Alignment.");
      });
    return () => { active = false; };
  }, [assessmentId]);

  const actions = useMemo(
    () => [...(state?.priorityActions ?? [])].sort((left, right) => left.order - right.order),
    [state]
  );
  const functionNames = useMemo(
    () => new Map((state?.functionalAlignment ?? []).map((item) => [item.id, item.functionName])),
    [state]
  );

  return (
    <AlignmentShell active="home" assessmentId={assessmentId} organisationName={context?.organisation.companyName}>
      {error ? <AlignmentError message={error} /> : !state || !context ? <AlignmentLoading /> : state.status !== "in_progress" ? (
        <section className="mx-auto max-w-xl py-20 text-center">
          <p className="text-xs font-semibold uppercase text-[#777]">Alignment not started</p>
          <h1 className="mt-4 text-3xl font-semibold">Complete the Stress Test handoff first.</h1>
          <p className="mt-4 leading-7 text-[#666]">Alignment is initialized from your agreed Define output and completed eight-point review.</p>
          <Link className="mt-7 inline-flex min-h-11 items-center bg-[#1f63f3] px-5 font-semibold text-white outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#1f63f3]" href={`/assessments/${assessmentId}/stress-test`}>Return to Stress Test</Link>
        </section>
      ) : (
        <>
          <header className="flex flex-col gap-5 border-b border-[#dedede] pb-7 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm text-[#777]">Your business <span aria-hidden="true">/</span> Alignment</p>
              <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">Hello, {context.organisation.companyName || "there"}</h1>
              <p className="mt-2 max-w-3xl text-[#696969]">How your organisation is lining up around <PurposeName context={context} /> and what needs attention next.</p>
            </div>
            <Link className="inline-flex min-h-11 shrink-0 items-center justify-center border border-[#cfcfcf] bg-white px-4 text-sm font-semibold outline-none hover:border-[#1f63f3] focus-visible:ring-2 focus-visible:ring-[#1f63f3]" href={`/assessments/${assessmentId}/align/progress`}>View progress</Link>
          </header>

          <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(260px,0.72fr)_minmax(0,1.45fr)]">
            <section className="border border-[#dedede] bg-white p-6" aria-labelledby="overview-heading">
              <p className="text-xs font-semibold uppercase text-[#858585]">How aligned are we right now?</p>
              <h2 className="mt-2 text-xl font-semibold" id="overview-heading">Alignment overview</h2>
              <div className="mt-8 border-l-4 border-[#1f63f3] pl-5">
                <p className="text-3xl font-semibold">Not calculated</p>
                <p className="mt-2 text-sm leading-6 text-[#696969]">No approved Alignment Score methodology is available. The findings below show the recorded qualitative state.</p>
              </div>
              <dl className="mt-8 grid grid-cols-2 gap-4 border-t border-[#e3e3e3] pt-5">
                <div><dt className="text-xs text-[#777]">Functions reviewed</dt><dd className="mt-1 text-2xl font-semibold">{state.functionalAlignment.length}</dd></div>
                <div><dt className="text-xs text-[#777]">Open gaps</dt><dd className="mt-1 text-2xl font-semibold">{state.gaps.filter((gap) => gap.status !== "completed").length}</dd></div>
              </dl>
            </section>

            <section className="bg-[#1f63f3] p-6 text-white" aria-labelledby="priority-heading">
              <p className="text-xs font-semibold uppercase text-blue-100">Priority / What should we do next?</p>
              {actions.length ? (
                <div className="mt-5">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-blue-100">
                    <span>{actions[0].adopted ? "Adopted" : "Proposed"}</span>
                    <span aria-hidden="true">·</span>
                    <span>{actions[0].status.replaceAll("-", " ")}</span>
                  </div>
                  <h2 className="mt-3 max-w-3xl text-2xl font-semibold sm:text-3xl" id="priority-heading">{actions[0].title}</h2>
                  <p className="mt-3 max-w-3xl text-base leading-7 text-blue-50">{actions[0].rationale}</p>
                  {actions[0].relatedFunctionId && functionNames.get(actions[0].relatedFunctionId) ? <p className="mt-5 text-sm text-blue-100">Related area: {functionNames.get(actions[0].relatedFunctionId)}</p> : null}
                  {actions.length > 1 ? <p className="mt-5 border-t border-blue-400 pt-4 text-sm text-blue-100">{actions.length - 1} more ordered action{actions.length === 2 ? "" : "s"} recorded</p> : null}
                </div>
              ) : <EmptyCopy title="No priority action recorded" copy="Alignment has no evidence-supported priority action yet." inverse />}
            </section>
          </div>

          <section className="mt-5 border border-[#dedede] bg-white p-6" aria-labelledby="functions-heading">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div><p className="text-xs font-semibold uppercase text-[#858585]">Where are we aligned?</p><h2 className="mt-2 text-xl font-semibold" id="functions-heading">Functional alignment</h2></div>
              <p className="text-sm text-[#777]">Qualitative findings, not function scores</p>
            </div>
            {state.functionalAlignment.length ? (
              <ul className="mt-6 grid gap-px bg-[#dedede] md:grid-cols-2">
                {state.functionalAlignment.map((item) => (
                  <li className="bg-white p-5" key={item.id}>
                    <div className="flex items-start justify-between gap-4">
                      <h3 className="font-semibold">{item.functionName}</h3>
                      <span className={`shrink-0 border-l-2 pl-2 text-xs font-semibold ${findingStyles[item.status]}`}>{findingLabels[item.status]}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-[#666]">{item.reasoning}</p>
                    <p className="mt-4 text-xs text-[#858585]">{item.gapIds.length} related gap{item.gapIds.length === 1 ? "" : "s"} · {item.actionIds.length} action{item.actionIds.length === 1 ? "" : "s"}</p>
                  </li>
                ))}
              </ul>
            ) : <EmptyCopy title="No functional findings yet" copy="The backend has not recorded functional alignment findings for this assessment." />}
          </section>

          <section className="mt-5 border border-[#dedede] bg-white p-6" aria-labelledby="gaps-heading">
            <p className="text-xs font-semibold uppercase text-[#858585]">What are our biggest gaps?</p>
            <h2 className="mt-2 text-xl font-semibold" id="gaps-heading">Gaps and tensions</h2>
            {state.gaps.length ? (
              <ul className="mt-6 grid gap-4 lg:grid-cols-2">
                {state.gaps.map((gap) => (
                  <li className="border-l-4 border-[#c93838] bg-[#fafafa] p-5" key={gap.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="font-semibold">{gap.title}</h3><span className="text-xs font-semibold uppercase text-[#777]">{gap.status.replaceAll("-", " ")}</span></div>
                    <p className="mt-3 text-sm leading-6 text-[#5f5f5f]">{gap.description}</p>
                    <p className="mt-4 text-sm"><span className="font-semibold">Why it matters:</span> {gap.whyItMatters}</p>
                    {gap.suggestedNextAction ? <p className="mt-3 text-sm"><span className="font-semibold">Suggested next action:</span> {gap.suggestedNextAction}</p> : null}
                    {gap.relatedFunctionId && functionNames.get(gap.relatedFunctionId) ? <p className="mt-4 text-xs text-[#777]">Related area: {functionNames.get(gap.relatedFunctionId)}</p> : null}
                  </li>
                ))}
              </ul>
            ) : <EmptyCopy title="No gaps recorded" copy="No evidence-supported Alignment gaps are currently present." />}
          </section>
        </>
      )}
    </AlignmentShell>
  );
}

function PurposeName({ context }: { context: AlignmentContext }) {
  const statement = context.define.output?.agreedSoi?.statement;
  return <strong className="font-semibold text-[#202020]">{statement ? `“${statement}”` : "the agreed purpose framework"}</strong>;
}

function EmptyCopy({ title, copy, inverse = false }: { title: string; copy: string; inverse?: boolean }) {
  return <div className="mt-6"><h3 className="font-semibold">{title}</h3><p className={`mt-2 text-sm leading-6 ${inverse ? "text-blue-100" : "text-[#777]"}`}>{copy}</p></div>;
}
