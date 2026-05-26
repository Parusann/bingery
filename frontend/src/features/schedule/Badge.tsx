export type BadgeType = "sub" | "dub";

export function Badge({ type, size = "md" }: { type: BadgeType; size?: "sm" | "md" }) {
  const label = type.toUpperCase();
  const isSub = type === "sub";
  const color = isSub ? "text-peach" : "text-sage";
  const bg = isSub ? "bg-peach/10" : "bg-sage/10";
  const border = isSub ? "border-peach/40" : "border-sage/40";
  const dotColor = isSub ? "bg-peach" : "bg-sage";
  const text = size === "sm" ? "text-[9.5px]" : "text-[11px]";
  return (
    <span
      className={`${color} ${bg} ${border} ${text} font-mono uppercase tracking-[0.18em] inline-flex items-center gap-[5px] rounded px-[9px] py-[4px] border`}
    >
      <span className={`${dotColor} h-[5px] w-[5px] rounded-full shadow-[0_0_5px_currentColor]`} />
      {label}
    </span>
  );
}
