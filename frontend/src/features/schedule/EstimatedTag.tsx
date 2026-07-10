import { Info } from "lucide-react";

const TOOLTIP =
  "Dub date is an approximate placeholder (~8 weeks after the sub release), not a confirmed schedule.";

export function EstimatedTag() {
  return (
    <span
      title={TOOLTIP}
      className="inline-flex items-center gap-1 rounded-pill border border-dashed border-line-2 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.1em] text-mute cursor-help"
    >
      <Info className="h-3 w-3" aria-hidden />
      estimated
    </span>
  );
}
