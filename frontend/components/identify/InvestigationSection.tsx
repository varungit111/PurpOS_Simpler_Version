import { InvestigationSectionData } from "@/data/identify-investigation";
import { InvestigationCard } from "./InvestigationCard";

type InvestigationSectionProps = {
  section: InvestigationSectionData;
  assessmentId?: string;
};

export function InvestigationSection({
  section,
  assessmentId
}: InvestigationSectionProps) {
  return (
    <section aria-labelledby={`${section.id}-title`} className="min-w-0">
      <div className="mb-4 grid grid-cols-[auto_1fr_auto] items-center gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-purpos-violet">
          {section.eyebrow}
        </p>
        <h2
          id={`${section.id}-title`}
          className="text-sm font-bold uppercase tracking-normal text-purpos-ink"
        >
          {section.title}
        </h2>
        <p className="text-xs font-medium text-slate-500">{section.completion}</p>
      </div>

      <div className="grid gap-4">
        {section.activities.map((activity) => (
          <InvestigationCard
            activity={activity}
            assessmentId={assessmentId}
            key={activity.id}
          />
        ))}
      </div>
    </section>
  );
}
