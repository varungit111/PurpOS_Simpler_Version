import { ConfidenceMetric } from "@/data/identify-investigation";
import type { PlaybookCoverage } from "@/lib/identify-board";

type ConfidenceScorecardProps = {
  overall: number;
  caption: string;
  metrics: ConfidenceMetric[];
  playbookCoverage?: PlaybookCoverage[];
};

export function ConfidenceScorecard({
  overall,
  caption,
  metrics,
  playbookCoverage = []
}: ConfidenceScorecardProps) {
  return (
    <aside
      aria-labelledby="confidence-scorecard-title"
      className="mx-auto mt-10 w-full max-w-[1500px] rounded-2xl border border-slate-200 bg-white p-6"
    >
      <div className="grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div>
          <h2
            id="confidence-scorecard-title"
            className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500"
          >
            Confidence Scorecard
          </h2>

          <div className="mt-4 flex items-end gap-3">
            <p className="text-5xl font-bold leading-none text-purpos-ink">
              {overall}%
            </p>
            <p className="max-w-28 pb-1 text-sm leading-4 text-slate-600">
              {caption}
            </p>
          </div>

          <div
            aria-label={`Overall confidence ${overall}%`}
            className="mt-6 h-1.5 rounded-full bg-slate-200"
            role="img"
          >
            <div
              className="h-1.5 rounded-full bg-purpos-violet"
              style={{ width: `${overall}%` }}
            />
          </div>

          <div className="mt-7 grid gap-4">
            {metrics.map((metric) => (
              <div key={metric.label}>
                <div className="mb-2 flex items-center justify-between gap-4">
                  <p className="text-sm font-medium text-purpos-ink">
                    {metric.label}
                  </p>
                  <p className="text-xs font-medium text-slate-500">
                    {metric.value}%
                  </p>
                </div>
                <div
                  aria-label={`${metric.label} confidence ${metric.value}%`}
                  className="h-1.5 rounded-full bg-slate-200"
                  role="img"
                >
                  <div
                    className="h-1.5 rounded-full bg-purpos-violet"
                    style={{ width: `${metric.value}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-xs font-bold uppercase tracking-[0.28em] text-slate-500">
            Playbook Coverage
          </h3>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {playbookCoverage.length === 0 ? (
              <p className="text-sm leading-6 text-slate-500">
                Coverage will appear after the board state loads.
              </p>
            ) : (
              playbookCoverage.map((item) => (
                <div
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                  key={item.areaId}
                  title={item.question}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-sm font-semibold text-purpos-ink">
                      {item.label}
                    </p>
                    <CoverageDot status={item.status} />
                  </div>
                  <p className="mt-2 text-xs font-medium text-slate-500">
                    {coverageLabel(item.status)} - {item.evidenceIds.length}{" "}
                    evidence item
                    {item.evidenceIds.length === 1 ? "" : "s"}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

function CoverageDot({ status }: { status: PlaybookCoverage["status"] }) {
  return (
    <span
      aria-label={coverageLabel(status)}
      className={`size-2.5 shrink-0 rounded-full ${
        status === "sufficient"
          ? "bg-emerald-500"
          : status === "partial"
            ? "bg-purpos-violet"
            : "bg-slate-300"
      }`}
    />
  );
}

function coverageLabel(status: PlaybookCoverage["status"]) {
  if (status === "sufficient") {
    return "Sufficient";
  }
  if (status === "partial") {
    return "Partial";
  }
  return "Uncovered";
}
