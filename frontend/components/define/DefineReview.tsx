"use client";
import { useAssessmentSession, useStageReviewMode } from "@/components/assessment/AssessmentSessionContext";
import { agreeDefineSoi, completeDefine, getDefine, getDefineCompletion, type DefineReadiness, type DefineState } from "@/lib/define";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useCallback } from "react";
import { ApprovalBadge, DefineNotice, DefineShell } from "./DefineShell";

export function DefineReview({ assessmentId }: { assessmentId: string }) {
  const router = useRouter();
  const session = useAssessmentSession();
  const reviewOnly = useStageReviewMode("define");
  const [define, setDefine] = useState<DefineState | null>(null);
  const [readiness, setReadiness] = useState<DefineReadiness | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { const [d, r] = await Promise.all([getDefine(assessmentId), getDefineCompletion(assessmentId)]); setDefine(d); setReadiness(r); }, [assessmentId]);
  useEffect(() => { load().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load Define review.")); }, [load]);
  async function agreeSoi() { setBusy(true); try { const soi = await agreeDefineSoi(assessmentId); setDefine((current) => current ? { ...current, soiCandidate: soi } : current); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to agree the SOI."); } finally { setBusy(false); } }
  async function finish() { setBusy(true); setError(null); try { await completeDefine(assessmentId); router.push(`/assessments/${assessmentId}/stress-test`); } catch (caught) { setError(caught instanceof Error ? caught.message : "Define is not ready to complete."); await load().catch(() => undefined); } finally { setBusy(false); } }
  return <DefineShell accent="green" assessmentId={assessmentId} descriptor="Ready for the hard questions" section="Define review">
    <div className="flex flex-1 flex-col py-12">
      <h1 className="text-4xl font-normal sm:text-5xl">Review the idea before it is tested.</h1>
      <p className="mt-4 max-w-3xl text-lg leading-8 text-[#776e67]">The Stress Test uses only the agreed Define output and its linked evidence.</p>
      {!define || !readiness ? <div className="mt-12 h-48 animate-pulse bg-[#eadfd4]" /> : <>
        <div className="mt-10 grid gap-px bg-[#d8d0c8] md:grid-cols-2">
          <ReviewItem title="Single Organizing Idea" status={define.soiCandidate?.approvalStatus}><p>{define.soiCandidate?.statement ?? "Missing"}</p>{!reviewOnly && define.soiCandidate && define.soiCandidate.approvalStatus !== "agreed" ? <button className="mt-4 font-bold text-[#27765f] underline" disabled={busy} onClick={() => void agreeSoi()} type="button">Agree this SOI</button> : null}</ReviewItem>
          <ReviewItem title="Positioning Statement" status={define.positioning.approvalStatus}><p>{define.positioning.composedStatement ?? "Incomplete positioning"}</p><Link className="mt-4 inline-block font-bold text-[#27765f] underline" href={`/assessments/${assessmentId}/define/positioning`}>Review positioning</Link></ReviewItem>
          <ReviewItem title="Core Values" status={define.values.some((item) => item.approvalStatus === "agreed") ? "agreed" : "ai-proposed"}><p>{define.values.filter((item) => item.approvalStatus === "agreed").length} agreed of {define.values.length}</p><Link className="mt-4 inline-block font-bold text-[#27765f] underline" href={`/assessments/${assessmentId}/define/values`}>Review values</Link></ReviewItem>
          <ReviewItem title="Moments of Truth" status={define.moments.some((item) => item.approvalStatus === "agreed") ? "agreed" : "ai-proposed"}><p>{define.moments.filter((item) => item.approvalStatus === "agreed").length} agreed of {define.moments.length}</p><Link className="mt-4 inline-block font-bold text-[#27765f] underline" href={`/assessments/${assessmentId}/define/moments`}>Review moments</Link></ReviewItem>
        </div>
        {readiness.blockingIssues.length ? <section className="mt-8 border-l-2 border-[#c35353] pl-5"><h2 className="font-bold">Resolve before completion</h2><ul className="mt-3 grid gap-2 text-sm text-[#776e67]">{readiness.blockingIssues.map((item) => <li key={item.code}>{item.message}</li>)}</ul></section> : null}
        {readiness.openQuestions.length ? <details className="mt-7"><summary className="cursor-pointer font-bold">Non-blocking open questions ({readiness.openQuestions.length})</summary><ul className="mt-3 grid gap-2 text-sm">{readiness.openQuestions.map((item) => <li key={item}>{item}</li>)}</ul></details> : null}
        {error ? <DefineNotice>{error}</DefineNotice> : null}
        <div className="mt-10 flex justify-end">
          {reviewOnly ? (
            session?.stage === "stress_test" ? <Link className="inline-flex min-h-12 items-center bg-[#2f8b73] px-6 font-bold text-white outline-none focus-visible:ring-2 focus-visible:ring-[#2f8b73] focus-visible:ring-offset-4" href={`/assessments/${assessmentId}/stress-test`}>Return to Stress Test <span aria-hidden="true" className="ml-2">-&gt;</span></Link> : null
          ) : <button className="min-h-12 bg-[#2f8b73] px-6 font-bold text-white disabled:opacity-40" disabled={busy || !readiness.canComplete} onClick={() => void finish()} type="button">{busy ? "Completing..." : "Complete Define and begin Stress Test"} <span aria-hidden="true">-&gt;</span></button>}
        </div>
      </>}
    </div>
  </DefineShell>;
}

function ReviewItem({ children, status, title }: { children: React.ReactNode; status?: "ai-proposed" | "user-edited" | "agreed"; title: string }) { return <section className="bg-[#fbf4ec] p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">{title}</h2>{status ? <ApprovalBadge status={status} /> : null}</div><div className="mt-5 leading-7 text-[#665f59]">{children}</div></section>; }
