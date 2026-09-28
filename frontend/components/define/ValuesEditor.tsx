"use client";

import { getDefine, updateDefineValue, type ValueCommitment } from "@/lib/define";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ApprovalBadge, DefineNotice, DefineShell } from "./DefineShell";

export function ValuesEditor({ assessmentId }: { assessmentId: string }) {
  const [values, setValues] = useState<ValueCommitment[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftMeaning, setDraftMeaning] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
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
        setValues(payload.values);
        setActiveId(payload.values[0]?.id ?? null);
      })
      .catch((caught) => {
        if (isMounted) setError(caught instanceof Error ? caught.message : "Unable to load values.");
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => { isMounted = false; };
  }, [assessmentId]);

  const activeIndex = values.findIndex((value) => value.id === activeId);
  const activeValue = activeIndex >= 0 ? values[activeIndex] : null;

  function selectValue(value: ValueCommitment) {
    setActiveId(value.id);
    setIsEditing(false);
    setError(null);
    setMessage(null);
  }

  function startEditing() {
    if (!activeValue) return;
    setDraftName(activeValue.name);
    setDraftMeaning(activeValue.meaning ?? "");
    setIsEditing(true);
    setMessage(null);
  }

  async function save(approvalStatus: "user-edited" | "agreed") {
    if (!activeValue) return;
    const name = isEditing ? draftName.trim() : activeValue.name;
    const meaning = isEditing ? draftMeaning.trim() : activeValue.meaning;
    if (!name || !meaning) {
      setError("Add both a commitment name and its meaning before saving.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await updateDefineValue(assessmentId, activeValue.id, { name, meaning, approvalStatus });
      setValues((current) => current.map((value) => value.id === saved.id ? saved : value));
      setIsEditing(false);
      setMessage(approvalStatus === "agreed" ? "Commitment agreed and saved." : "Your edits are saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save this value.");
    } finally {
      setIsSaving(false);
    }
  }

  function move(direction: -1 | 1) {
    if (!values.length) return;
    const nextIndex = Math.min(values.length - 1, Math.max(0, activeIndex + direction));
    selectValue(values[nextIndex]);
  }

  return (
    <DefineShell accent="pink" assessmentId={assessmentId} descriptor="Your commitments" section="Values">
      <div className="flex flex-1 flex-col py-10 sm:py-14">
        {isLoading ? (
          <div aria-label="Loading values" className="grid flex-1 content-center gap-6" role="status"><span className="h-24 w-2/3 animate-pulse bg-[#eadfd4]" /><span className="h-28 w-full max-w-3xl animate-pulse bg-[#eadfd4]" /></div>
        ) : error && values.length === 0 ? (
          <div className="my-auto text-center"><h1 className="text-3xl font-semibold">Values are not available.</h1><DefineNotice>{error}</DefineNotice></div>
        ) : values.length === 0 ? (
          <div className="my-auto text-center"><h1 className="text-3xl font-semibold">No commitments were proposed.</h1><p className="mt-4 text-[#776e67]">The saved Define state does not currently contain any values.</p></div>
        ) : activeValue ? (
          <>
            <div className="grid flex-1 items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.9fr)] xl:gap-16">
              <section>
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <p className="text-sm font-bold tracking-[0.2em] text-[#cd4c94]">{String(activeIndex + 1).padStart(2, "0")} / {String(values.length).padStart(2, "0")}</p>
                  <ApprovalBadge status={activeValue.approvalStatus} />
                </div>
                {isEditing ? (
                  <div className="mt-8 grid gap-5">
                    <label><span className="text-xs font-bold uppercase tracking-[0.18em] text-[#847a71]">Commitment</span><input className="mt-2 w-full border-b-2 border-[#cd4c94] bg-transparent py-2 text-4xl font-semibold outline-none focus:bg-white/35 sm:text-6xl" onChange={(event) => setDraftName(event.target.value)} value={draftName} /></label>
                    <label><span className="text-xs font-bold uppercase tracking-[0.18em] text-[#847a71]">Meaning</span><textarea className="mt-2 min-h-36 w-full resize-y border border-[#d8cec4] bg-white/45 p-4 text-lg leading-8 outline-none focus:ring-2 focus:ring-[#cd4c94]" onChange={(event) => setDraftMeaning(event.target.value)} value={draftMeaning} /></label>
                  </div>
                ) : (
                  <><h1 className="mt-8 break-words text-6xl font-semibold leading-none tracking-normal sm:text-8xl lg:text-9xl">{activeValue.name}</h1><p className="mt-8 max-w-3xl text-xl leading-9 text-[#5e5960] sm:text-2xl sm:leading-10">{activeValue.meaning ?? "No meaning was included with this proposal."}</p></>
                )}
                {activeValue.supportingEvidence.length ? <p className="mt-7 border-l-2 border-[#cd4c94] pl-4 text-sm leading-6 text-[#776e67]">{activeValue.supportingEvidence[0]}</p> : null}
                {error ? <DefineNotice>{error}</DefineNotice> : null}
                {message ? <DefineNotice tone="success">{message}</DefineNotice> : null}
                <div className="mt-8 flex flex-wrap gap-3">
                  {isEditing ? <button className="min-h-11 border border-[#cd4c94] px-5 font-bold text-[#aa3878] disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={() => void save("user-edited")} type="button">{isSaving ? "Saving..." : "Save edits"}</button> : <button className="min-h-11 border border-[#cd4c94] px-5 font-bold text-[#aa3878]" data-stage-mutation onClick={startEditing} type="button">Edit commitment</button>}
                  <button className="min-h-11 bg-[#cd4c94] px-5 font-bold text-white disabled:opacity-50" data-stage-mutation disabled={isSaving} onClick={() => void save("agreed")} type="button">Agree</button>
                </div>
              </section>
              <div aria-hidden="true" className="relative aspect-[4/3] w-full overflow-hidden bg-[#5d604b] shadow-[18px_20px_35px_rgba(52,45,38,0.16)]">
                <div className="absolute inset-6 border border-white/20 sm:inset-9" />
                <span className="absolute bottom-7 right-8 text-7xl font-semibold text-white/12 sm:text-8xl">{String(activeIndex + 1).padStart(2, "0")}</span>
              </div>
            </div>

            <nav aria-label="Values" className="mt-10 flex flex-col gap-6 border-t border-[#d8d0c8] pt-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="flex max-w-full gap-8 overflow-x-auto pb-2">
                {values.map((value) => <button aria-current={value.id === activeValue.id ? "step" : undefined} className={`shrink-0 border-b-2 pb-2 text-lg ${value.id === activeValue.id ? "border-[#cd4c94] font-bold text-[#292624]" : "border-transparent text-[#998f86]"}`} key={value.id} onClick={() => selectValue(value)} type="button">{value.name}</button>)}
              </div>
              <div className="flex shrink-0 gap-3 self-end">
                <button aria-label="Previous commitment" className="grid size-12 place-items-center rounded-full border border-[#d2c9c0] text-xl disabled:opacity-30" disabled={activeIndex === 0} onClick={() => move(-1)} type="button">&lt;-</button>
                <button aria-label="Next commitment" className="grid size-12 place-items-center rounded-full bg-[#cd4c94] text-xl text-white disabled:opacity-30" disabled={activeIndex === values.length - 1} onClick={() => move(1)} type="button">-&gt;</button>
              </div>
            </nav>
            <div className="mt-7 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <Link className="font-bold text-[#aa3878] underline underline-offset-4" href={`/assessments/${assessmentId}/define/positioning`}>&lt;- Back to Positioning</Link>
              <Link className="inline-flex min-h-12 items-center justify-center bg-[#2f8b73] px-6 font-bold text-white outline-none hover:bg-[#267761] focus-visible:ring-2 focus-visible:ring-[#2f8b73] focus-visible:ring-offset-4 focus-visible:ring-offset-[#fbf4ec]" href={`/assessments/${assessmentId}/define/moments`}>Continue to Value Chain <span aria-hidden="true" className="ml-3">-&gt;</span></Link>
            </div>
          </>
        ) : null}
      </div>
    </DefineShell>
  );
}
