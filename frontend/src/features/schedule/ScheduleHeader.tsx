import { FilterPills } from "./FilterPills";

type Lang = "sub" | "dub" | "both";

export function ScheduleHeader({
  lang,
  myShowsOnly,
  onLangChange,
  onMineToggle,
}: {
  lang: Lang;
  myShowsOnly: boolean;
  onLangChange: (v: Lang) => void;
  onMineToggle: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between pt-14 pb-7">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-peach">
          The release calendar
        </p>
        <h1 className="font-display italic text-[clamp(48px,5vw,76px)] leading-none tracking-tight">
          <span className="bg-gradient-to-b from-ink to-ink-2 bg-clip-text text-transparent">
            What's
          </span>{" "}
          <span className="bg-gradient-to-b from-peach to-peach-deep bg-clip-text text-transparent">
            airing
          </span>
        </h1>
      </div>
      <FilterPills
        lang={lang}
        myShowsOnly={myShowsOnly}
        onLangChange={onLangChange}
        onMineToggle={onMineToggle}
      />
    </header>
  );
}
