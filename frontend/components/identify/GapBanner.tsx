type GapBannerProps = {
  title: string;
  description: string;
};

export function GapBanner({ title, description }: GapBannerProps) {
  return (
    <aside
      aria-labelledby="biggest-gap-title"
      className="grid gap-4 rounded-lg border border-purpos-line bg-purpos-lilac/65 p-5 sm:grid-cols-[auto_1fr_auto] sm:items-center"
    >
      <div
        aria-hidden="true"
        className="grid size-10 place-items-center rounded-lg border border-purpos-line bg-white text-sm font-semibold text-purpos-violet"
      >
        !
      </div>
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-purpos-violet">
          Biggest gap right now
        </p>
        <h2
          id="biggest-gap-title"
          className="mt-1 text-base font-semibold leading-6 text-purpos-ink"
        >
          {title}
        </h2>
        <p className="mt-1 text-sm leading-5 text-slate-600">{description}</p>
      </div>
      <button
        className="inline-flex min-h-11 items-center justify-center rounded-lg bg-purpos-violet px-5 text-sm font-semibold text-white shadow-sm outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-purpos-violet focus-visible:ring-offset-2"
        type="button"
      >
        Send invites <span aria-hidden="true" className="ml-2">-&gt;</span>
      </button>
    </aside>
  );
}
