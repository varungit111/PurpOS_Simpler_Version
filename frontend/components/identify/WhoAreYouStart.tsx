"use client";

import { createAssessmentSession } from "@/lib/sessions";
import { rememberAssessment } from "@/lib/assessment-pointer";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function WhoAreYouStart() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [website, setWebsite] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedCompanyName = companyName.trim();
    const trimmedWebsite = website.trim();

    if (!trimmedCompanyName || !trimmedWebsite || isStarting) {
      return;
    }

    setIsStarting(true);
    setError(null);

    try {
      const session = await createAssessmentSession({
        companyName: trimmedCompanyName,
        website: normalizeWebsite(trimmedWebsite)
      });
      rememberAssessment(session.id);
      router.push(`/assessments/${session.id}/identify/ai-detective/running`);
    } catch {
      setError("I couldn't save those details. Check the backend API.");
      setIsStarting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f3f6] text-purpos-ink">
      <header className="border-b border-slate-200 bg-white">
        <nav className="flex min-h-[72px] items-center justify-between px-6 sm:px-10">
          <div className="text-lg font-bold">PurpOS</div>
          <div className="text-xs font-bold uppercase tracking-[0.35em] text-slate-500">
            Identify - Stage 1 of 4
          </div>
        </nav>
      </header>

      <section className="grid min-h-[calc(100vh-72px)] place-items-center px-5 py-12">
        <form className="w-full max-w-3xl" onSubmit={handleSubmit}>
          <h1 className="text-center text-5xl font-bold tracking-normal text-[#29272d] sm:text-6xl">
            Who are you?
          </h1>

          <div className="mx-auto mt-10 grid max-w-[760px] overflow-hidden rounded-xl border border-slate-300 bg-white shadow-sm sm:grid-cols-[1fr_1fr_auto]">
            <label className="grid min-h-[70px] gap-1 border-b border-slate-200 px-7 py-4 sm:border-b-0 sm:border-r">
              <span className="text-[10px] font-bold uppercase tracking-[0.28em] text-slate-500">
                Company name
              </span>
              <input
                className="min-w-0 bg-transparent text-lg font-medium outline-none placeholder:text-slate-300"
                disabled={isStarting}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="Meridian Joinery"
                required
                value={companyName}
              />
            </label>

            <label className="grid min-h-[70px] gap-1 border-b border-slate-200 px-7 py-4 sm:border-b-0 sm:border-r">
              <span className="text-[10px] font-bold uppercase tracking-[0.28em] text-slate-500">
                Website
              </span>
              <input
                className="min-w-0 bg-transparent text-lg font-medium outline-none placeholder:text-slate-300"
                disabled={isStarting}
                inputMode="url"
                onChange={(event) => setWebsite(event.target.value)}
                placeholder="meridianjoinery.co.uk"
                required
                value={website}
              />
            </label>

            <div className="grid p-3">
              <button
                className="inline-flex min-h-14 min-w-32 items-center justify-center rounded-lg bg-purpos-violet px-7 text-base font-semibold text-white shadow-sm outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
                disabled={
                  isStarting || !companyName.trim() || !website.trim()
                }
                type="submit"
              >
                {isStarting ? "Starting..." : "Start"}
                <span aria-hidden="true" className="ml-3">
                  -&gt;
                </span>
              </button>
            </div>
          </div>

          {error ? (
            <p className="mx-auto mt-5 max-w-xl text-center text-sm font-medium text-red-700">
              {error}
            </p>
          ) : null}
        </form>
      </section>
    </main>
  );
}

function normalizeWebsite(value: string): string {
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  return `https://${value}`;
}
