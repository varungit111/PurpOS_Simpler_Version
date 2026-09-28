"use client";

import { getDefine, type DefineState } from "@/lib/define";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ApprovalBadge, DefineNotice, DefineShell } from "./DefineShell";
import { splitSoiStatement } from "./define-presentation";

export function DefineReveal({ assessmentId }: { assessmentId: string }) {
  const [define, setDefine] = useState<DefineState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getDefine(assessmentId)
      .then((payload) => {
        if (isMounted) setDefine(payload);
      })
      .catch((caught) => {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Unable to load Define.");
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [assessmentId]);

  const soi = define?.soiCandidate;
  const statement = soi?.statement ? splitSoiStatement(soi.statement) : null;

  return (
    <DefineShell
      accent="violet"
      assessmentId={assessmentId}
      descriptor="Your guiding star"
      section="Single Organizing Idea"
    >
      <div className="flex flex-1 flex-col py-10 sm:py-14 lg:py-10">
        {isLoading ? (
          <div aria-label="Loading Define proposal" className="grid gap-5" role="status">
            <span className="h-5 w-40 animate-pulse bg-[#e8ded4]" />
            <span className="h-28 w-full max-w-5xl animate-pulse bg-[#e8ded4]" />
            <span className="h-5 w-2/3 animate-pulse bg-[#e8ded4]" />
          </div>
        ) : error ? (
          <div className="mx-auto max-w-xl text-center">
            <h1 className="text-3xl font-semibold">Define could not be opened.</h1>
            <DefineNotice>{error} Your Identify progress has not been changed.</DefineNotice>
            <Link className="mt-8 inline-flex font-bold text-[#7a56b3] underline" href={`/assessments/${assessmentId}/identify/brief`}>
              Return to your Identify Brief
            </Link>
          </div>
        ) : define?.status === "not_started" ? (
          <div className="mx-auto max-w-xl text-center">
            <h1 className="text-3xl font-semibold">Define has not started yet.</h1>
            <p className="mt-4 leading-7 text-[#776e67]">Start it from your completed Identify Brief so the proposal is created from the persisted handoff.</p>
            <Link className="mt-8 inline-flex font-bold text-[#7a56b3] underline" href={`/assessments/${assessmentId}/identify/brief`}>
              Open Identify Brief
            </Link>
          </div>
        ) : !soi?.statement ? (
          <div className="mx-auto max-w-xl text-center">
            <h1 className="text-3xl font-semibold">No organizing idea was proposed.</h1>
            <DefineNotice>The Define proposal is saved, but it does not contain a Single Organizing Idea.</DefineNotice>
          </div>
        ) : (
          <div className="flex flex-1 flex-col">
            <div className="flex justify-end"><ApprovalBadge status={soi.approvalStatus} /></div>
            {soi.guidingStar ? (
              <div className="mx-auto mt-8 w-full max-w-xl text-center lg:mr-[6%]">
                <p className="px-5 text-lg leading-8 text-[#7a56b3] sm:text-xl">{soi.guidingStar}</p>
                <div className="mt-5 border-b border-[#a98bd0]" />
                <div className="mx-auto h-3 w-px bg-[#a98bd0]" />
              </div>
            ) : null}
            <h1 className="my-auto flex flex-wrap items-baseline justify-center gap-x-[0.22em] break-words py-10 text-center text-6xl font-semibold uppercase leading-[0.88] tracking-normal sm:text-8xl lg:text-[9rem] xl:text-[10rem]">
              <span>{statement?.lead}</span>
              {statement?.accent ? <span className="text-[#7a56b3]">{statement.accent}</span> : null}
            </h1>
            {soi.meaning ? (
              <div className="mx-auto w-full max-w-4xl text-center lg:ml-[5%]">
                <div className="mx-auto h-3 w-px bg-[#c9bfce]" />
                <div className="border-t border-[#c9bfce]" />
                <p className="mx-auto max-w-3xl px-5 pt-5 text-lg leading-8 text-[#746a62]">{soi.meaning}</p>
              </div>
            ) : null}
            <div className="mt-10 flex justify-end border-t border-[#ded5cc] pt-6">
              <Link className="inline-flex min-h-12 items-center bg-[#7a56b3] px-6 font-bold text-white outline-none hover:bg-[#6846a2] focus-visible:ring-2 focus-visible:ring-[#7a56b3] focus-visible:ring-offset-4 focus-visible:ring-offset-[#fbf4ec]" href={`/assessments/${assessmentId}/define/positioning`}>
                Positioning statement <span aria-hidden="true" className="ml-3">-&gt;</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </DefineShell>
  );
}
