import type { IdentifyActivity } from "@/data/identify-investigation";
import Link from "next/link";
import { ActivityStatusBadge } from "./ActivityStatusBadge";

type InvestigationCardProps = {
  activity: IdentifyActivity;
  assessmentId?: string;
};

const activityRoutes: Record<string, string> = {
  "ai-detective": "ai-detective",
  "company-cards": "company-cards",
  "day-in-their-shoes": "day-in-their-shoes",
  "discover-synthesis": "discover-synthesis",
  "evidence-wall": "evidence-wall",
  "hot-seat": "hot-seat",
  "identify-brief": "brief",
  "listen-summary": "listen-summary",
  "perception-gaps": "perception-gaps",
  "signal-hunt": "signal-hunt",
  "where-do-you-stand": "where-do-you-stand",
  "who-matters": "who-matters"
};

export function InvestigationCard({
  activity,
  assessmentId
}: InvestigationCardProps) {
  const isLocked = activity.status === "locked";
  const actionLabel = activity.actionLabel;
  const activityDetail =
    activity.progressLabel ??
    (typeof activity.durationMinutes === "number"
      ? `~${activity.durationMinutes} min`
      : activity.helperText);
  const routeSegment = activityRoutes[activity.id];
  const activityHref =
    routeSegment && assessmentId && !isLocked
      ? `/assessments/${assessmentId}/identify/${routeSegment}`
      : null;
  const tone = cardTone(activity.section, activity.status);

  return (
    <article
      aria-labelledby={`${activity.id}-title`}
      className={`flex min-h-[260px] min-w-0 flex-col border p-5 text-white shadow-sm transition ${tone}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-white/80">
          {activity.section}
        </p>
        <ActivityStatusBadge status={activity.status} />
      </div>

      <h3
        id={`${activity.id}-title`}
        className="mt-10 break-words text-2xl font-semibold leading-tight tracking-normal text-white"
      >
        {activity.title}
      </h3>
      <p className="mt-3 break-words text-sm leading-6 text-white/90">
        {activity.description}
      </p>

      <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-7">
        <p className="min-w-0 text-sm text-white/85">{activityDetail}</p>
        {activityHref && actionLabel ? (
          <Link
            className="inline-flex min-h-10 shrink-0 items-center bg-white px-4 py-2 text-sm font-semibold text-purpos-violet outline-none transition hover:bg-white/90 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2"
            href={activityHref}
          >
            {actionLabel} <span aria-hidden="true">-&gt;</span>
          </Link>
        ) : actionLabel ? (
          <button
            className="inline-flex min-h-10 shrink-0 items-center bg-white/80 px-4 py-2 text-sm font-semibold text-purpos-violet outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2"
            disabled={isLocked}
            type="button"
          >
            {actionLabel} <span aria-hidden="true">-&gt;</span>
          </button>
        ) : null}
      </div>
    </article>
  );
}

function cardTone(
  section: IdentifyActivity["section"],
  status: IdentifyActivity["status"]
) {
  if (status === "locked") {
    return "border-[#cbbbe8] bg-[#c5b2e7]/85";
  }
  if (section === "discover") {
    return "border-[#d98035] bg-[#d98235]";
  }
  if (section === "listen") {
    return "border-[#c8579e] bg-[#c8579e]";
  }
  return "border-[#a98fe0] bg-[#bca8e8]";
}
