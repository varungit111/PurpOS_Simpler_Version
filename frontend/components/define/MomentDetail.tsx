"use client";

import {
  getDefine,
  momentStatusOptions,
  updateDefineMoment,
  type ValueChainMoment
} from "@/lib/define";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApprovalBadge, DefineNotice, DefineShell } from "./DefineShell";
import { MomentStatusBadge } from "./MomentStatusBadge";

type MomentDraft = Pick<
  ValueChainMoment,
  "name" | "question" | "today" | "desiredState" | "theMove" | "status"
>;

export function MomentDetail({
  assessmentId,
  momentId
}: {
  assessmentId: string;
  momentId: string;
}) {
  const router = useRouter();
  const [moments, setMoments] = useState<ValueChainMoment[]>([]);
  const [soiStatement, setSoiStatement] = useState<string | null>(null);
  const [moment, setMoment] = useState<ValueChainMoment | null>(null);
  const [draft, setDraft] = useState<MomentDraft | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getDefine(assessmentId)
      .then((payload) => {
        if (!isMounted) return;
        if (payload.status === "not_started") {
          setError("Define has not started. Return to the Identify Brief to begin.");
          return;
        }
        const selected = payload.moments.find((item) => item.id === momentId);
        setMoments(payload.moments);
        setSoiStatement(payload.soiCandidate?.statement ?? null);
        if (!selected) {
          setError("This Moment of Truth does not exist in the saved Define state.");
          return;
        }
        setMoment(selected);
        setDraft(toDraft(selected));
      })
      .catch((caught) => {
        if (isMounted) setError(caught instanceof Error ? caught.message : "Unable to load this moment.");
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => { isMounted = false; };
  }, [assessmentId, momentId]);

  useEffect(() => {
    if (!isDirty) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [isDirty]);

  const activeIndex = moments.findIndex((item) => item.id === momentId);

  function updateDraft(field: keyof MomentDraft, value: string) {
    setDraft((current) => current ? { ...current, [field]: value } : current);
    setIsDirty(true);
    setMessage(null);
  }

  function cancelEditing() {
    if (!moment) return;
    setDraft(toDraft(moment));
    setIsEditing(false);
    setIsDirty(false);
    setError(null);
  }

  async function save(approvalStatus: "user-edited" | "agreed") {
    if (!moment || !draft) return false;
    if (!draft.name.trim()) {
      setError("The moment name cannot be empty.");
      return false;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await updateDefineMoment(assessmentId, moment.id, {
        name: draft.name.trim(),
        question: nullableText(draft.question),
        today: nullableText(draft.today),
        desiredState: nullableText(draft.desiredState),
        theMove: nullableText(draft.theMove),
        status: draft.status,
        approvalStatus
      });
      setMoment(saved);
      setDraft(toDraft(saved));
      setMoments((current) => current.map((item) => item.id === saved.id ? saved : item));
      setIsEditing(false);
      setIsDirty(false);
      setMessage(approvalStatus === "agreed" ? "Moment agreed and saved." : "Your moment edits are saved.");
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save this moment.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function navigate(path: string) {
    if (isDirty && !window.confirm("Leave without saving your moment edits?")) return;
    router.push(path);
  }

  return (
    <DefineShell accent="green" assessmentId={assessmentId} descriptor="Where we live the idea" section="Value Chain - Moments of Truth">
      <div className="flex flex-1 flex-col py-9 sm:py-12">
        {isLoading ? (
          <div aria-label="Loading Moment of Truth" className="grid flex-1 content-center gap-6" role="status"><span className="h-12 w-3/4 animate-pulse bg-[#eadfd4]" /><div className="grid gap-5 md:grid-cols-2"><span className="h-48 animate-pulse bg-[#eadfd4]" /><span className="h-48 animate-pulse bg-[#eadfd4]" /></div></div>
        ) : error && !moment ? (
          <div className="my-auto text-center"><h1 className="text-3xl font-semibold">Moment unavailable.</h1><DefineNotice>{error}</DefineNotice><button className="mt-7 font-bold text-[#27765f] underline underline-offset-4" onClick={() => navigate(`/assessments/${assessmentId}/define/moments`)} type="button">Return to Value Chain</button></div>
        ) : moment && draft ? (
          <div className="flex flex-1 flex-col">
            <div className="mb-9">
              <h1 className="max-w-5xl break-words text-4xl font-normal leading-tight sm:text-5xl">{soiStatement ?? "Moment of Truth"}</h1>
              <p className="mt-3 text-lg leading-7 text-[#8d8379]">See where this moment stands, and how to close the gap.</p>
            </div>
            <div className="grid flex-1 gap-8 xl:grid-cols-[minmax(0,2fr)_minmax(20rem,0.85fr)]">
            <article className="min-w-0 border-t border-[#5c554f] pt-7">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-4">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#2f8b73]">Moment {String(activeIndex + 1).padStart(2, "0")} - {moment.name}</p>
                  <MomentStatusBadge status={moment.status} />
                </div>
                <ApprovalBadge status={moment.approvalStatus} />
              </div>

              {isEditing ? (
                <div className="mt-8 grid gap-6">
                  <Field label="Moment name"><input className={inputClass} onChange={(event) => updateDraft("name", event.target.value)} value={draft.name} /></Field>
                  <Field label="Moment question"><textarea className={textareaClass} onChange={(event) => updateDraft("question", event.target.value)} value={draft.question ?? ""} /></Field>
                  <fieldset>
                    <legend className={labelClass}>Status</legend>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {momentStatusOptions.map((option) => <label className={`cursor-pointer border px-4 py-3 text-sm font-bold ${draft.status === option.value ? "border-[#2f8b73] bg-[#dcefe9] text-[#27765f]" : "border-[#d5ccc3] bg-white/40 text-[#756b62]"}`} key={option.value}><input checked={draft.status === option.value} className="sr-only" name="moment-status" onChange={() => updateDraft("status", option.value)} type="radio" value={option.value} />{option.label}</label>)}
                    </div>
                  </fieldset>
                  <div className="grid gap-5 md:grid-cols-2">
                    <Field label="Today"><textarea className={textareaClass} onChange={(event) => updateDraft("today", event.target.value)} value={draft.today ?? ""} /></Field>
                    <Field label="The desired standard"><textarea className={textareaClass} onChange={(event) => updateDraft("desiredState", event.target.value)} value={draft.desiredState ?? ""} /></Field>
                  </div>
                  <Field label="The Move"><textarea className={textareaClass} onChange={(event) => updateDraft("theMove", event.target.value)} value={draft.theMove ?? ""} /></Field>
                </div>
              ) : (
                <>
                  <h2 className="mt-8 max-w-5xl break-words text-4xl font-normal leading-tight sm:text-5xl">{moment.question ?? moment.name}</h2>
                  <div className="mt-9 grid gap-5 md:grid-cols-[1fr_auto_1fr] md:items-stretch">
                    <StatePanel label="Today" text={moment.today} tone="today" />
                    <span aria-hidden="true" className="hidden items-center text-2xl text-[#2f8b73] md:flex">-&gt;</span>
                    <StatePanel label="The desired standard" text={moment.desiredState} tone="desired" />
                  </div>
                  <section className="mt-7 grid gap-3 border-l-2 border-[#2f8b73] pl-5 sm:grid-cols-[8rem_1fr]">
                    <h2 className="text-xs font-bold uppercase tracking-[0.22em] text-[#2f8b73]">The Move <span aria-hidden="true">-&gt;</span></h2>
                    <p className="text-lg leading-8 text-[#5d5860]">{moment.theMove ?? "No move was included with this proposal."}</p>
                  </section>
                  {moment.supportingEvidence.length ? (
                    <details className="mt-8 border-t border-[#ddd4cb] pt-5"><summary className="cursor-pointer text-sm font-bold text-[#27765f]">Supporting context</summary><ul className="mt-4 grid gap-2 text-sm leading-6 text-[#776e67]">{moment.supportingEvidence.map((item) => <li className="border-l-2 border-[#b8cfc6] pl-4" key={item}>{item}</li>)}</ul></details>
                  ) : null}
                </>
              )}

              {error ? <DefineNotice>{error}</DefineNotice> : null}
              {message ? <DefineNotice tone="success">{message}</DefineNotice> : null}

              <div className="mt-9 flex flex-col-reverse gap-3 border-t border-[#ddd4cb] pt-6 sm:flex-row sm:items-center sm:justify-between">
                <button className="min-h-11 border border-[#cfc5bb] px-5 font-bold" onClick={() => navigate(`/assessments/${assessmentId}/define/moments`)} type="button">&lt;- Value Chain</button>
                <div className="flex flex-wrap gap-3">
                  {isEditing ? <><button className="min-h-11 border border-[#cfc5bb] px-5 font-bold disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={cancelEditing} type="button">Cancel</button><button className="min-h-11 border border-[#2f8b73] px-5 font-bold text-[#27765f] disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={() => void save("user-edited")} type="button">{isSaving ? "Saving..." : "Save edits"}</button></> : <button className="min-h-11 border border-[#2f8b73] px-5 font-bold text-[#27765f]" data-stage-mutation onClick={() => setIsEditing(true)} type="button">Edit moment</button>}
                  <button className="min-h-11 bg-[#2f8b73] px-5 font-bold text-white disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={() => void save("agreed")} type="button">Agree</button>
                </div>
              </div>
            </article>

            <aside aria-label="Other Moments of Truth" className="border-t border-[#5c554f] xl:border-l xl:border-t-0">
              <ol className="flex overflow-x-auto xl:block xl:overflow-visible">
                {moments.map((item, index) => (
                  <li className="min-w-52 border-r border-[#ddd4cb] p-5 xl:min-w-0 xl:border-b xl:border-r-0" key={item.id}>
                    <button aria-current={item.id === moment.id ? "step" : undefined} className="w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-[#2f8b73]" onClick={() => navigate(`/assessments/${assessmentId}/define/moments/${item.id}`)} type="button">
                      <span className="text-xs font-bold tracking-[0.18em] text-[#2f8b73]">{String(index + 1).padStart(2, "0")}</span>
                      <span className="mt-3 block font-semibold leading-5">{item.name}</span>
                      <span className="mt-4 block"><MomentStatusBadge status={item.status} /></span>
                    </button>
                  </li>
                ))}
              </ol>
              <div className="mt-5 flex justify-end gap-3 px-2">
                <button aria-label="Previous moment" className="grid size-11 place-items-center rounded-full border border-[#cfc5bb] disabled:opacity-30" disabled={activeIndex <= 0} onClick={() => navigate(`/assessments/${assessmentId}/define/moments/${moments[activeIndex - 1]?.id}`)} type="button">&lt;-</button>
                <button aria-label="Next moment" className="grid size-11 place-items-center rounded-full bg-[#2f8b73] text-white disabled:opacity-30" disabled={activeIndex < 0 || activeIndex >= moments.length - 1} onClick={() => navigate(`/assessments/${assessmentId}/define/moments/${moments[activeIndex + 1]?.id}`)} type="button">-&gt;</button>
              </div>
            </aside>
            </div>
          </div>
        ) : null}
      </div>
    </DefineShell>
  );
}

function StatePanel({ label, text, tone }: { label: string; text: string | null; tone: "today" | "desired" }) {
  return <section className="min-h-44 border border-[#d8d0c8] bg-white/65 p-6"><h2 className={`text-xs font-bold uppercase tracking-[0.22em] ${tone === "today" ? "text-[#c35353]" : "text-[#2f8b73]"}`}>{label}</h2><p className="mt-4 text-base leading-7">{text ?? "Not provided in this proposal."}</p></section>;
}

function Field({ children, label }: { children: React.ReactNode; label: string }) {
  return <label><span className={labelClass}>{label}</span>{children}</label>;
}

const labelClass = "text-xs font-bold uppercase tracking-[0.2em] text-[#2f8b73]";
const inputClass = "mt-2 min-h-12 w-full border border-[#d8cec4] bg-white/65 px-4 text-lg outline-none focus:ring-2 focus:ring-[#2f8b73]";
const textareaClass = "mt-2 min-h-32 w-full resize-y border border-[#d8cec4] bg-white/65 p-4 text-base leading-7 outline-none focus:ring-2 focus:ring-[#2f8b73]";

function toDraft(moment: ValueChainMoment): MomentDraft {
  return { name: moment.name, question: moment.question, today: moment.today, desiredState: moment.desiredState, theMove: moment.theMove, status: moment.status };
}

function nullableText(value: string | null) {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}
