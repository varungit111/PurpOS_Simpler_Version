import Link from "next/link";

type IdentifyJourneyHeaderProps = {
  assessmentId: string;
  backHref: string;
  current: "discover" | "board";
  confidence: number | null;
};

export function IdentifyJourneyHeader({
  assessmentId,
  backHref,
  current,
  confidence
}: IdentifyJourneyHeaderProps) {
  const boardHref = `/assessments/${assessmentId}/identify`;
  const nextHref = current === "board" ? `${boardHref}#identify-brief` : boardHref;
  const journeyItems = [
    { label: "Welcome", href: "/" },
    { label: "Identify", href: "/identify/who-are-you" },
    { label: "Discover", href: `${boardHref}#discover` },
    { label: "Listen", href: `${boardHref}#listen` },
    { label: "Understand", href: `${boardHref}#understand` },
    { label: "Define", href: `/assessments/${assessmentId}/define` }
  ];

  return (
    <header className="relative z-20">
      <div className="bg-[#29262d] text-white">
        <nav className="mx-auto grid min-h-12 max-w-[1600px] grid-cols-[auto_1fr_auto] items-center gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-4 text-sm font-semibold">
            <Link className="outline-none hover:text-white/75 focus-visible:underline" href={backHref}>
              &lt;- Back
            </Link>
            <Link
              className={current === "board" ? "text-white" : "text-white/65 hover:text-white"}
              href={boardHref}
            >
              Board
            </Link>
          </div>

          <ol className="hidden items-center justify-center gap-5 text-xs font-semibold text-white/55 lg:flex">
            {journeyItems.map((item) => (
              <li key={item.label}>
                <Link
                  className={`outline-none hover:text-white focus-visible:underline ${
                    item.label === "Discover" ? "text-white" : ""
                  }`}
                  href={item.href}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ol>

          <div className="flex items-center justify-end gap-4 text-sm font-semibold">
            <Link className="text-white/70 hover:text-white" href={nextHref}>
              Next -&gt;
            </Link>
            <Link className="text-white/70 hover:text-white" href="/">
              Close
            </Link>
          </div>
        </nav>
      </div>

      <div className="border-b border-[#d8d2ca] bg-[#fffdf9]">
        <nav className="mx-auto flex min-h-16 max-w-[1600px] items-center gap-5 px-4 sm:px-6">
          <Link className="shrink-0 text-lg font-bold" href="/">
            PurpOS
          </Link>
          <span className="hidden h-6 w-px bg-[#d8d2ca] sm:block" />
          <span className="shrink-0 text-xs font-bold uppercase tracking-[0.18em] text-[#6d655f]">
            Identify
          </span>
          <div className="min-w-0 flex-1 overflow-x-auto [scrollbar-width:none]">
            <ol className="flex min-w-max items-center gap-5 px-1 text-sm font-semibold text-[#8b827a]">
              <li>
                <Link className="text-[#d67832]" href={`${boardHref}#discover`}>
                  01 Discover
                </Link>
              </li>
              <li>
                <Link href={`${boardHref}#listen`}>02 Listen</Link>
              </li>
              <li>
                <Link href={`${boardHref}#understand`}>03 Understand</Link>
              </li>
            </ol>
          </div>
          <div className="hidden shrink-0 items-center gap-2 text-sm font-semibold text-[#5f5853] sm:flex">
            <span className="size-2 rounded-full bg-[#7455b7]" />
            {confidence === null ? "Building confidence" : `Confidence ${confidence}%`}
          </div>
        </nav>
      </div>
    </header>
  );
}
