import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { Collection } from "@/types/models";
import { Badge } from "@/design/Badge";
import { transitions } from "@/design/motion";

export function CollectionCard({
  collection,
  index = 0,
}: {
  collection: Collection;
  index?: number;
}) {
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
        <div className="relative aspect-[5/3] bg-black/40 overflow-hidden">
          {collection.cover_image_url ? (
            <img
              src={collection.cover_image_url}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-amber/20 via-transparent to-violet/20" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2">
            <h3 className="font-display text-xl truncate">{collection.title}</h3>
            {collection.is_public ? (
              <Badge color="#8fc9a4">Public</Badge>
            ) : (
              <Badge color="#b89ac4">Private</Badge>
            )}
          </div>
        </div>
        <div className="p-3 text-sm text-text-muted flex items-center justify-between">
          <span>{collection.item_count} anime</span>
          <span className="font-mono text-xs">
            {new Date(collection.updated_at).toLocaleDateString()}
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
