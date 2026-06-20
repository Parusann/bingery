import { Info } from "lucide-react";

const TOOLTIP =
  "Dub date is an approximate placeholder (~8 weeks after the sub release), not a confirmed schedule.";

export function EstimatedTag() {
  return (
    <span
      title={TOOLTIP}
      className="inline-flex items-center gap-[3px] rounded-full border border-dashed border-line-2 px-[7px] py-[2px] text-[9.5px] font-mono uppercase tracking-[0.1em] text-mute cursor-help"
    >
      <Info className="h-3 w-3" />
      estimated
    </span>
  );
}
