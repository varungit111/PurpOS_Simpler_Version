"use client";

import {
  generateDefine,
  getDefine,
  updateDefinePositioning,
  type PositioningStatement
} from "@/lib/define";
import {
  useAssessmentSession,
  useStageReviewMode
} from "@/components/assessment/AssessmentSessionContext";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ApprovalBadge, DefineNotice, DefineShell } from "./DefineShell";
import {
  composePositioningStatement,
  organisationDisplayName
} from "./define-presentation";

const emptyPositioning: PositioningStatement = {
  audience: null,
  categoryContext: null,
  capabilityValue: null,
  reasonBelievability: null,
  composedStatement: null,
  evidenceIds: [],
  provenance: {
    status: "ai-inferred",
    rationale: null,
    generatedAt: null,
    updatedAt: null,
    sourceHandoff: null
  },
  approvalStatus: "ai-proposed"
};

export function PositioningEditor({ assessmentId }: { assessmentId: string }) {
  const router = useRouter();
  const session = useAssessmentSession();
  const reviewOnly = useStageReviewMode("define");
  const [positioning, setPositioning] = useState(emptyPositioning);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    let isMounted = true;
    const loadDefine = reviewOnly ? getDefine : generateDefine;
    loadDefine(assessmentId)
      .then((payload) => {
        if (isMounted) {
          if (payload.status === "not_started") {
            setError("Define has not started. Return to the Identify Brief to begin.");
          } else {
            setPositioning(payload.positioning);
            setCompanyName(session.organisation.companyName);
          }
        }
      })
      .catch((caught) => {
        if (isMounted) setError(errorMessage(caught, "Unable to load positioning."));
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [assessmentId, reviewOnly, session]);

  const composedStatement = useMemo(
    () => composePositioningStatement(organisationDisplayName(companyName), positioning),
    [companyName, positioning]
  );
  const organisationName = organisationDisplayName(companyName);

  function updateField(
    field: "audience" | "categoryContext" | "capabilityValue" | "reasonBelievability",
    value: string
  ) {
    setPositioning((current) => ({ ...current, [field]: value }));
    setMessage(null);
  }

  async function save(approvalStatus: "user-edited" | "agreed") {
    if (!positioning.audience?.trim() || !positioning.categoryContext?.trim() || !positioning.capabilityValue?.trim() || !positioning.reasonBelievability?.trim()) {
      setError("Complete all four parts before saving the positioning statement.");
      return false;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await updateDefinePositioning(assessmentId, {
        audience: positioning.audience.trim(),
        categoryContext: positioning.categoryContext.trim(),
        capabilityValue: positioning.capabilityValue.trim(),
        reasonBelievability: positioning.reasonBelievability.trim(),
        composedStatement,
        approvalStatus
      });
      setPositioning(saved);
      setMessage(approvalStatus === "agreed" ? "Positioning agreed and saved." : "Your edits are saved.");
      return true;
    } catch (caught) {
      setError(errorMessage(caught, "Unable to save positioning."));
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function agreeAndContinue() {
    const didSave = await save("agreed");
    if (didSave) router.push(`/assessments/${assessmentId}/define/values`);
  }

  return (
    <DefineShell accent="orange" assessmentId={assessmentId} descriptor="Your elevator pitch" section="Positioning Statement">
      <div className="flex flex-1 flex-col py-10 sm:py-14">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <h1 className="text-3xl font-normal text-[#91877d] sm:text-4xl">Craft it, slot by slot.</h1>
          {!isLoading ? <ApprovalBadge status={positioning.approvalStatus} /> : null}
        </div>

        {isLoading ? (
          <div aria-label="Loading positioning statement" className="mt-14 grid gap-5" role="status">
            {["82%", "60%", "74%", "88%"].map((width) => <span className="h-16 animate-pulse bg-[#eadfd4]" key={width} style={{ width }} />)}
          </div>
        ) : error && positioning === emptyPositioning ? (
          <DefineNotice>{error}</DefineNotice>
        ) : (
          <form className="mt-10 flex flex-1 flex-col" onSubmit={(event) => { event.preventDefault(); void save("user-edited"); }}>
            <div className="grid max-w-7xl gap-6 text-2xl leading-tight text-[#90877e] sm:gap-7 sm:text-4xl">
              <ScaffoldRow label="For" name="audience" value={positioning.audience ?? ""} onChange={(value) => updateField("audience", value)} />
              <ScaffoldRow label={`${organisationName} is the`} name="category" suffix="that" value={positioning.categoryContext ?? ""} onChange={(value) => updateField("categoryContext", value)} />
              <ScaffoldRow label="" name="capability" suffix="- because" value={positioning.capabilityValue ?? ""} onChange={(value) => updateField("capabilityValue", value)} />
              <ScaffoldRow label="" name="reason" value={positioning.reasonBelievability ?? ""} onChange={(value) => updateField("reasonBelievability", value)} />
            </div>

            <section className="mt-10 max-w-5xl border-l-2 border-[#df8137] pl-5">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#df8137]">Composed statement</p>
              <p className="mt-3 max-w-4xl text-lg leading-8 text-[#5e5751]">{composedStatement || "Complete each slot to shape the statement."}</p>
            </section>

            {error ? <DefineNotice>{error}</DefineNotice> : null}
            {message ? <DefineNotice tone="success">{message}</DefineNotice> : null}

            <div className="mt-12 flex flex-col-reverse gap-3 border-t border-[#ddd4cb] pt-7 sm:flex-row sm:items-center sm:justify-between">
              <Link className="inline-flex min-h-11 items-center justify-center border border-[#cfc5bb] px-5 font-bold outline-none hover:bg-white/50 focus-visible:ring-2 focus-visible:ring-[#df8137]" href={`/assessments/${assessmentId}/define`}>
                <span aria-hidden="true" className="mr-3">&lt;-</span> Back
              </Link>
              <div className="flex flex-col gap-3 sm:flex-row">
                <button className="min-h-11 border border-[#df8137] px-5 font-bold text-[#bd6628] outline-none hover:bg-white/50 focus-visible:ring-2 focus-visible:ring-[#df8137] disabled:opacity-50" data-stage-mutation disabled={isSaving} type="submit">{isSaving ? "Saving..." : "Save edits"}</button>
                <button className="min-h-11 bg-[#df8137] px-5 font-bold text-white outline-none hover:bg-[#c96f2d] focus-visible:ring-2 focus-visible:ring-[#df8137] focus-visible:ring-offset-4 disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={() => void agreeAndContinue()} type="button">Agree and continue <span aria-hidden="true" className="ml-2">-&gt;</span></button>
              </div>
            </div>
          </form>
        )}
        {positioning.approvalStatus === "agreed" && !isLoading ? (
          <div className="mt-5 flex justify-end"><Link className="font-bold text-[#bd6628] underline underline-offset-4" href={`/assessments/${assessmentId}/define/values`}>Continue to Values</Link></div>
        ) : null}
      </div>
    </DefineShell>
  );
}

function ScaffoldRow({ label, name, onChange, suffix, value }: { label: string; name: string; onChange: (value: string) => void; suffix?: string; value: string }) {
  return (
    <label className="flex flex-col gap-3 sm:flex-row sm:items-center">
      {label ? <span className="shrink-0">{label}</span> : null}
      <span className="relative min-w-0 flex-1">
        <input aria-label={name} className="min-h-16 w-full border-0 bg-[#f5dcc0] px-5 py-3 text-xl text-[#292624] outline-none ring-[#df8137] placeholder:text-[#8f8275] focus:ring-2 sm:text-3xl" onChange={(event) => onChange(event.target.value)} value={value} />
        <span aria-hidden="true" className="absolute right-4 top-1/2 -translate-y-1/2 text-base text-[#df8137]">&#9998;</span>
      </span>
      {suffix ? <span className="shrink-0">{suffix}</span> : null}
    </label>
  );
}

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error ? caught.message : fallback;
}
