import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { Collection } from "@/types/models";
import { Badge } from "@/design/Badge";
import { transitions } from "@/design/motion";

// Map the stored `color` token to a Tailwind gradient pair.
const COLOR_GRADIENTS: Record<string, string> = {
  amber: "from-amber/35 via-amber/10 to-transparent",
  violet: "from-violet/40 via-violet/10 to-transparent",
  indigo: "from-indigo-400/30 via-indigo-400/10 to-transparent",
  rose: "from-rose-400/35 via-rose-400/10 to-transparent",
  emerald: "from-emerald-400/30 via-emerald-400/10 to-transparent",
};

export function CollectionCard({
  collection,
  index = 0,
}: {
  collection: Collection;
  index?: number;
}) {
  const gradient =
    COLOR_GRADIENTS[collection.color] ?? COLOR_GRADIENTS.amber;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transitions.ease, delay: Math.min(index, 10) * 0.03 }}
    >
      <Link
        to={`/collections/${collection.id}`}
        className="block rounded-xl overflow-hidden border border-border bg-surface hover:border-border-strong transition-colors glass-edge"
      >
        <div className="relative aspect-[5/3] overflow-hidden">
          <div className={`absolute inset-0 bg-gradient-to-br ${gradient}`} />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2">
            <h3 className="font-display text-xl truncate">{collection.name}</h3>
            {collection.is_public ? (
              <Badge color="#8fc9a4">Public</Badge>
            ) : (
              <Badge color="#b89ac4">Private</Badge>
            )}
          </div>
        </div>
        <div className="p-3 text-sm text-text-muted flex items-center justify-between">
          <span>{collection.items_count} anime</span>
          <span className="font-mono text-xs">
            {new Date(collection.updated_at).toLocaleDateString()}
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
