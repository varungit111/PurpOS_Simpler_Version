import {
  IdentifyActivityStatus,
  statusLabels
} from "@/data/identify-investigation";

type ActivityStatusBadgeProps = {
  status: IdentifyActivityStatus;
};

const statusStyles: Record<IdentifyActivityStatus, string> = {
  completed: "border-slate-200 bg-white text-slate-500",
  "ai-running": "border-purpos-line bg-purpos-lilac text-purpos-violet",
  "invite-team": "border-slate-200 bg-white text-slate-700",
  "needs-user": "border-slate-200 bg-white text-purpos-ink",
  locked: "border-slate-200 bg-white text-slate-500",
  conditional: "border-purpos-line bg-white text-purpos-violet",
  "ready-for-review": "border-purpos-line bg-purpos-lilac text-purpos-violet",
  available: "border-slate-200 bg-white text-slate-700"
};

const statusDots: Record<IdentifyActivityStatus, string> = {
  completed: "bg-slate-300",
  "ai-running": "bg-purpos-violet",
  "invite-team": "bg-slate-300",
  "needs-user": "bg-purpos-ink",
  locked: "bg-slate-300",
  conditional: "bg-purpos-violet",
  "ready-for-review": "bg-purpos-violet",
  available: "bg-emerald-500"
};

export function ActivityStatusBadge({ status }: ActivityStatusBadgeProps) {
  const isLocked = status === "locked";

  return (
    <span
      className={`inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium leading-none ${statusStyles[status]}`}
    >
      {isLocked ? (
        <span aria-hidden="true" className="text-[10px] leading-none">
          L
        </span>
      ) : (
        <span
          aria-hidden="true"
          className={`size-1.5 rounded-full ${statusDots[status]}`}
        />
      )}
      {statusLabels[status]}
    </span>
  );
}
