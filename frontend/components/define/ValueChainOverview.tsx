"use client";

import { getDefine, type ValueChainMoment } from "@/lib/define";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DefineNotice, DefineShell } from "./DefineShell";
import { MomentStatusBadge } from "./MomentStatusBadge";
import { valueChainHeading } from "./define-presentation";

export function ValueChainOverview({ assessmentId }: { assessmentId: string }) {
  const [moments, setMoments] = useState<ValueChainMoment[]>([]);
  const [soi, setSoi] = useState<{ statement: string | null; meaning: string | null } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getDefine(assessmentId)
      .then((payload) => {
        if (!isMounted) return;
        if (payload.status === "not_started") {
          setError("Define has not started. Return to the Identify Brief to begin.");
          return;
        }
        setMoments(payload.moments);
        setSoi(payload.soiCandidate);
      })
      .catch((caught) => {
        if (isMounted) setError(caught instanceof Error ? caught.message : "Unable to load the Value Chain.");
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => { isMounted = false; };
  }, [assessmentId]);

  return (
    <DefineShell accent="green" assessmentId={assessmentId} descriptor="Where we live the idea" section="Value Chain - Moments of Truth">
      <div className="flex flex-1 flex-col py-10 sm:py-14">
        <div>
          <h1 className="max-w-5xl break-words text-4xl font-normal leading-tight sm:text-5xl">{valueChainHeading(soi?.statement)}</h1>
          <p className="mt-3 max-w-4xl text-lg leading-7 text-[#8d8379]">{soi?.meaning ?? "Every moment where the organizing idea can add value, or lose it."}</p>
        </div>

        {isLoading ? (
          <div aria-label="Loading Value Chain" className="mt-16 grid grid-cols-2 gap-px bg-[#ddd4cb] lg:grid-cols-4" role="status">
            {Array.from({ length: 4 }).map((_, index) => <span className="h-72 animate-pulse bg-[#eee5dc]" key={index} />)}
          </div>
        ) : error ? (
          <DefineNotice>{error}</DefineNotice>
        ) : moments.length === 0 ? (
          <section className="my-auto py-16 text-center">
            <h2 className="text-3xl font-semibold">No Moments of Truth were proposed.</h2>
            <p className="mt-4 text-[#776e67]">The saved Define state does not contain Value Chain moments yet.</p>
          </section>
        ) : (
          <div aria-label="Moments of Truth" className="mt-12 overflow-x-auto border-y border-[#5c554f]" tabIndex={0}>
            <ol className="grid min-w-max auto-cols-[minmax(13rem,1fr)] grid-flow-col divide-x divide-[#ddd4cb] lg:min-w-full">
              {moments.map((moment, index) => (
                <li className="flex min-h-[27rem] w-[min(72vw,17rem)] flex-col px-5 py-7 lg:w-auto" key={moment.id}>
                  <p className="text-xs font-bold tracking-[0.18em] text-[#2f8b73]">{String(index + 1).padStart(2, "0")} <span aria-hidden="true">-&gt;</span></p>
                  <h2 className="mt-5 break-words text-xl font-semibold leading-6">{moment.name}</h2>
                  <p className="mt-4 line-clamp-5 text-sm leading-6 text-[#8b8178]">{moment.question ?? moment.today ?? "No summary was included with this proposal."}</p>
                  <div className="mt-auto pt-8"><MomentStatusBadge status={moment.status} /></div>
                  <Link aria-label={`Expand ${moment.name}`} className="mt-5 inline-flex min-h-10 items-center justify-between border-t border-[#d8cfc6] pt-4 text-sm font-bold text-[#2f8b73] outline-none focus-visible:ring-2 focus-visible:ring-[#2f8b73]" href={`/assessments/${assessmentId}/define/moments/${moment.id}`}>Expand <span aria-hidden="true">+</span></Link>
                </li>
              ))}
            </ol>
          </div>
        )}

        <div className="mt-8 flex items-center justify-between gap-5">
          <Link className="font-bold text-[#27765f] underline underline-offset-4" href={`/assessments/${assessmentId}/define/values`}>&lt;- Back to Values</Link>
          {moments.length ? <Link className="inline-flex min-h-11 items-center bg-[#2f8b73] px-5 font-bold text-white" href={`/assessments/${assessmentId}/define/review`}>Review Define <span aria-hidden="true" className="ml-2">-&gt;</span></Link> : null}
        </div>
      </div>
    </DefineShell>
  );
}
