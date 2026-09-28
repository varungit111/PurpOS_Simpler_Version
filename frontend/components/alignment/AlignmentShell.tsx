"use client";

import Link from "next/link";
import type { ReactNode } from "react";

type AlignmentShellProps = {
  assessmentId: string;
  active: "home" | "progress";
  organisationName?: string | null;
  children: ReactNode;
};

export function AlignmentShell({
  assessmentId,
  active,
  organisationName,
  children
}: AlignmentShellProps) {
  const navigation = [
    { id: "home", label: "Home", href: `/assessments/${assessmentId}/align` },
    { id: "progress", label: "Progress", href: `/assessments/${assessmentId}/align/progress` }
  ] as const;

  return (
    <main className="min-h-screen bg-[#252525] p-2 text-[#181818] sm:p-5">
      <div className="mx-auto min-h-[calc(100vh-1rem)] max-w-[1580px] bg-[#fafafa] sm:min-h-[calc(100vh-2.5rem)] lg:grid lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="border-b border-[#dedede] bg-[#f5f5f5] px-4 py-4 lg:flex lg:min-h-[calc(100vh-2.5rem)] lg:flex-col lg:border-b-0 lg:border-r lg:px-5 lg:py-7">
          <div className="flex items-center justify-between gap-4">
            <Link
              className="rounded-sm text-lg font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#1f63f3]"
              href={`/assessments/${assessmentId}/align`}
            >
              {organisationName || "Your business"}
            </Link>
            <span className="grid size-9 place-items-center border border-[#d4d4d4] bg-white text-sm font-semibold" aria-hidden="true">
              {(organisationName || "Y").slice(0, 1).toUpperCase()}
            </span>
          </div>

          <nav aria-label="Alignment navigation" className="mt-5">
            <ul className="grid grid-cols-2 gap-2 lg:grid-cols-1">
              {navigation.map((item) => (
                <li key={item.id}>
                  <Link
                    aria-current={active === item.id ? "page" : undefined}
                    className={`flex min-h-11 items-center px-3 text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-[#1f63f3] ${
                      active === item.id
                        ? "bg-[#1f63f3] text-white"
                        : "text-[#606060] hover:bg-white hover:text-[#171717]"
                    }`}
                    href={item.href}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="mt-5 border-t border-[#dedede] pt-5 lg:mt-7">
            <p className="px-3 text-xs font-semibold uppercase text-[#8a8a8a]">Assessment</p>
            <Link className="mt-2 block min-h-10 px-3 py-2 text-sm text-[#606060] outline-none hover:bg-white focus-visible:ring-2 focus-visible:ring-[#1f63f3]" href={`/assessments/${assessmentId}/define/review`}>
              Identify &amp; Define
            </Link>
            <p className="px-3 py-2 text-sm font-semibold text-[#171717]">Alignment</p>
            <button className="w-full cursor-not-allowed px-3 py-2 text-left text-sm text-[#a0a0a0]" disabled title="Decision Canvas arrives in the next stage of development" type="button">
              Canvas
            </button>
          </div>

          <div className="mt-auto hidden pt-10 text-xs leading-5 text-[#8a8a8a] lg:block">
            Alignment remains in progress. Results and Measure &amp; Learn are not active yet.
          </div>
        </aside>

        <div className="min-w-0 px-5 py-7 sm:px-8 lg:px-10 lg:py-9 xl:px-14">{children}</div>
      </div>
    </main>
  );
}

export function AlignmentLoading() {
  return (
    <div aria-live="polite" aria-busy="true">
      <div className="h-5 w-36 animate-pulse bg-[#e4e4e4]" />
      <div className="mt-5 h-10 max-w-lg animate-pulse bg-[#e4e4e4]" />
      <div className="mt-8 grid gap-5 xl:grid-cols-2">
        <div className="h-60 animate-pulse border border-[#e0e0e0] bg-white" />
        <div className="h-60 animate-pulse border border-[#e0e0e0] bg-white" />
      </div>
      <span className="sr-only">Loading Alignment</span>
    </div>
  );
}

export function AlignmentError({ message }: { message: string }) {
  return <p className="border-l-4 border-[#cf2e2e] bg-white px-5 py-4 text-sm text-[#8e1f1f]" role="alert">{message}</p>;
}
