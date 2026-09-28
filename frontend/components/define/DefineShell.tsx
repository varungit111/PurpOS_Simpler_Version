import Link from "next/link";
import type { ReactNode } from "react";

type DefineShellProps = {
  assessmentId: string;
  accent: "violet" | "orange" | "pink" | "green";
  section: string;
  descriptor: string;
  children: ReactNode;
};

const accentClasses = {
  violet: "text-[#7a56b3]",
  orange: "text-[#df8137]",
  pink: "text-[#cd4c94]",
  green: "text-[#2f8b73]"
};

export function DefineShell({
  assessmentId,
  accent,
  section,
  descriptor,
  children
}: DefineShellProps) {
  return (
    <main className="min-h-screen bg-[#272727] p-2 text-[#292624] sm:p-5 lg:p-7">
      <div className="mx-auto flex min-h-[calc(100vh-1rem)] max-w-[1760px] flex-col bg-[#fbf4ec] px-5 py-7 sm:min-h-[calc(100vh-2.5rem)] sm:px-10 sm:py-9 lg:min-h-[calc(100vh-3.5rem)] lg:px-20 lg:py-14">
        <header className="flex items-start justify-between gap-5">
          <div>
            <Link
              className={`rounded-sm text-xs font-bold uppercase tracking-[0.28em] outline-none focus-visible:ring-2 focus-visible:ring-current focus-visible:ring-offset-4 focus-visible:ring-offset-[#fbf4ec] sm:text-sm ${accentClasses[accent]}`}
              href={`/assessments/${assessmentId}/define`}
            >
              Stage 02 - Define
            </Link>
            <p className="mt-2 text-sm text-[#958b80] sm:text-base">{section}</p>
          </div>
          <p className="max-w-40 text-right text-sm italic text-[#9b9085] sm:text-base">
            {descriptor}
          </p>
        </header>
        {children}
      </div>
    </main>
  );
}

export function ApprovalBadge({
  status
}: {
  status: "ai-proposed" | "user-edited" | "agreed";
}) {
  const labels = {
    "ai-proposed": "AI proposal",
    "user-edited": "Edited by you",
    agreed: "Agreed"
  };
  return (
    <span className="inline-flex min-h-7 items-center border border-[#d8cec4] bg-white/45 px-3 text-[11px] font-bold uppercase tracking-[0.16em] text-[#756b62]">
      {labels[status]}
    </span>
  );
}

export function DefineNotice({
  children,
  tone = "error"
}: {
  children: ReactNode;
  tone?: "error" | "success";
}) {
  return (
    <p
      className={`mt-5 border-l-2 px-4 py-2 text-sm ${
        tone === "error"
          ? "border-red-500 text-red-800"
          : "border-emerald-600 text-emerald-800"
      }`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </p>
  );
}
