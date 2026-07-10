import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { Collection } from "@/types/models";
import { Badge } from "@/design/Badge";
import { palette } from "@/design/tokens";
import { transitions } from "@/design/motion";

// Collections render as anime box-sets on a shelf: a colored spine, a
// textured cover with a ghosted serif monogram, and the title printed on
// the cover. The stored `color` token picks the set's colorway (values
// retuned from raw Tailwind indigo/rose/emerald to the dusty ramp).
const COLORWAYS: Record<string, { spine: string; gradient: string }> = {
  amber: { spine: "#efab81", gradient: "from-amber/35 via-amber/10 to-transparent" },
  violet: { spine: "#b89ac4", gradient: "from-violet/40 via-violet/10 to-transparent" },
  indigo: { spine: "#8f9bc4", gradient: "from-[#8f9bc4]/35 via-[#8f9bc4]/10 to-transparent" },
  rose: { spine: "#e88fa2", gradient: "from-[#e88fa2]/35 via-[#e88fa2]/10 to-transparent" },
  emerald: { spine: "#83c4a8", gradient: "from-[#83c4a8]/30 via-[#83c4a8]/10 to-transparent" },
};

export function CollectionCard({
  collection,
  index = 0,
}: {
  collection: Collection;
  index?: number;
}) {
  const way = COLORWAYS[collection.color] ?? COLORWAYS.amber;
  const initial = (collection.name.trim()[0] ?? "•").toUpperCase();
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transitions.ease, delay: Math.min(index, 10) * 0.03 }}
    >
      <Link
        to={`/collections/${collection.id}`}
        className="group flex rounded-xl overflow-hidden border border-border bg-surface shadow-e2 transition-all duration-base ease-out hover:border-amber/35 hover:-translate-y-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        {/* spine */}
        <span
          aria-hidden
          className="w-2.5 shrink-0 opacity-80 transition-opacity duration-base group-hover:opacity-100"
          style={{
            background: `linear-gradient(to bottom, ${way.spine}, ${way.spine}66)`,
          }}
        />
        <div className="flex-1 min-w-0">
          <div className="relative aspect-[5/3] overflow-hidden">
            <div className={`absolute inset-0 bg-gradient-to-br ${way.gradient}`} />
            {/* cover texture */}
            <div
              aria-hidden
              className="absolute inset-0"
              style={{
                background:
                  "repeating-linear-gradient(45deg, rgba(255,255,255,0.03) 0 10px, transparent 10px 20px)",
              }}
            />
            {/* ghosted monogram */}
            <span
              aria-hidden
              className="absolute -right-1 -bottom-9 font-display italic text-[7.5rem] leading-none text-white/[0.08] select-none transition-colors duration-base group-hover:text-white/[0.12]"
            >
              {initial}
            </span>
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
            <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2">
              <h3 className="font-display text-heading truncate">{collection.name}</h3>
              {collection.is_public ? (
                <Badge color={palette.success}>Public</Badge>
              ) : (
                <Badge color={palette.violet}>Private</Badge>
              )}
            </div>
          </div>
          <div className="p-3 text-sm text-text-muted flex items-center justify-between">
            <span className="font-mono text-xs tnum">{collection.items_count} anime</span>
            <span className="font-mono text-xs tnum text-text-dim">
              {new Date(collection.updated_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
