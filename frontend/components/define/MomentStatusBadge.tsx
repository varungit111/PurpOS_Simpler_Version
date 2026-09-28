import {
  momentStatusOptions,
  type ValueChainMomentStatus
} from "@/lib/define";

const statusClasses: Record<ValueChainMomentStatus, string> = {
  "on-course": "bg-[#dcefe9] text-[#27765f]",
  "in-progress": "bg-[#f7dfc1] text-[#c46f2f]",
  "gap-to-close": "bg-[#f6dddd] text-[#c35353]"
};

export function momentStatusLabel(status: ValueChainMomentStatus) {
  return momentStatusOptions.find((option) => option.value === status)?.label ?? status;
}

export function MomentStatusBadge({ status }: { status: ValueChainMomentStatus }) {
  return (
    <span className={`inline-flex min-h-7 items-center px-3 text-[10px] font-bold uppercase tracking-[0.15em] ${statusClasses[status]}`}>
      {momentStatusLabel(status)}
    </span>
  );
}
