import { StartAssessmentButton } from "@/components/assessment/StartAssessmentButton";

const journeyStages = ["Identify", "Define", "Align", "Measure & Learn"];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#fbfaf8] px-5 py-8 text-purpos-ink sm:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col justify-center">
        <section className="mx-auto w-full max-w-5xl">
          <h1 className="max-w-4xl text-5xl font-bold leading-[1.08] tracking-normal text-[#292625] sm:text-6xl lg:text-7xl">
            Start driving business performance with PurpOS
          </h1>

          <div className="mt-16 grid gap-6 lg:grid-cols-[minmax(0,1fr)_repeat(3,10rem)]">
            <article className="rounded-2xl border border-[#ded8cf] bg-white p-7 shadow-sm">
              <div className="grid h-40 place-items-center overflow-hidden rounded-xl bg-purpos-violet">
                <div
                  aria-hidden="true"
                  className="grid size-28 place-items-center rounded-full border-[10px] border-white/35"
                >
                  <div className="grid size-20 place-items-center rounded-full border-[10px] border-white/45">
                    <div className="grid size-12 place-items-center rounded-full border-[10px] border-white/70">
                      <span className="size-5 rounded-full bg-white" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-8 grid gap-5 sm:grid-cols-[1fr_auto] sm:items-end">
                <div>
                  <h2 className="max-w-xl text-2xl font-bold tracking-normal">
                    Take a leap into a purpose-driven way of doing business.
                  </h2>
                  <p className="mt-5 max-w-md text-base leading-6 text-[#726b66]">
                    Align every decision, team and goal to the reason you exist.
                  </p>
                </div>
                <StartAssessmentButton />
              </div>
            </article>

            {journeyStages.slice(1).map((stage, index) => (
              <article
                className="flex min-h-52 flex-col justify-between rounded-2xl border border-[#ded8cf] bg-white p-7"
                key={stage}
              >
                <p
                  className={`text-sm font-semibold ${
                    index === 0
                      ? "text-[#d77d36]"
                      : index === 1
                        ? "text-[#c04c91]"
                        : "text-purpos-violet"
                  }`}
                >
                  {String(index + 1).padStart(2, "0")}
                </p>
                <div>
                  <h2 className="text-xl font-semibold tracking-normal">
                    {stage.replace(" & Learn", "")}
                  </h2>
                  <p className="mt-2 text-base leading-6 text-[#726b66]">
                    {stage === "Define"
                      ? "Name the purpose."
                      : stage === "Align"
                        ? "Aim the work at it."
                        : "Track the drift."}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
