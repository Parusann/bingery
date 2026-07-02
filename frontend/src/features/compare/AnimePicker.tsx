import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Star, X } from "lucide-react";
import { Input } from "@/design/Input";
import { useSearch } from "@/hooks/useSearch";
import { transitions } from "@/design/motion";
import type { AnimeSummary } from "@/types/models";

interface Props {
  label: string;
  value: AnimeSummary | null;
  onChange: (next: AnimeSummary | null) => void;
}

// A self-contained anime picker for the Compare page: search input that
// fans out a dropdown of matches; clicking a row "selects" the anime and
// collapses the picker into a compact card. Click the X to swap selection.
export function AnimePicker({ label, value, onChange }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement | null>(null);
  const { results, loading } = useSearch(q);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Picked state — show the selected anime as a card with a clear button.
  if (value) {
    return (
      <div className="rounded-lg border border-amber/25 bg-bg-elevated/60 shadow-e1 p-3 flex gap-3 items-start">
        {value.image_url ? (
          <img
            src={value.image_url}
            alt=""
            className="w-14 h-20 object-cover rounded-sm"
          />
        ) : (
          <div className="w-14 h-20 rounded-sm bg-surface" />
        )}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-micro uppercase text-amber mb-1">
            {label}
          </div>
          <div className="font-display text-body-lg leading-tight line-clamp-2">
            {value.title_english || value.title}
          </div>
          <div className="text-xs text-text-muted tnum mt-1 inline-flex items-center gap-1">
            {value.year ?? "—"}
            {value.api_score != null ? (
              <>
                {" · "}
                <Star className="h-3 w-3 text-gold" fill="currentColor" aria-hidden />
                {value.api_score.toFixed(1)}
              </>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            onChange(null);
            setQ("");
          }}
          className="grid place-items-center h-8 w-8 text-text-muted rounded-md transition-colors hover:text-text hover:bg-surface-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60"
          aria-label={`Clear ${label}`}
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <div ref={wrap} className="relative">
      <Input
        label={label}
        placeholder="Search anime…"
        value={q}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
      />
      <AnimatePresence>
        {open && (results.length > 0 || loading) ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={transitions.easeFast}
            className="absolute left-0 right-0 mt-2 rounded-lg border border-border-strong bg-bg-elevated/95 backdrop-blur-xl overflow-hidden z-20 shadow-e3"
          >
            {loading ? (
              <div className="p-3 text-caption text-text-muted animate-pulse">
                Searching…
              </div>
            ) : (
              results.slice(0, 8).map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => {
                    onChange(a);
                    setOpen(false);
                    setQ("");
                  }}
                  className="flex gap-3 w-full text-left p-2.5 transition-colors hover:bg-surface-strong focus-visible:outline-none focus-visible:bg-surface-strong"
                >
                  {a.image_url ? (
                    <img
                      src={a.image_url}
                      alt=""
                      className="w-10 h-14 object-cover rounded-sm"
                    />
                  ) : (
                    <div className="w-10 h-14 rounded-sm bg-surface" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium line-clamp-1">
                      {a.title_english || a.title}
                    </div>
                    <div className="text-xs text-text-dim tnum">
                      {a.year ?? "—"}
                      {a.api_score != null
                        ? ` · ${a.api_score.toFixed(1)}`
                        : ""}
                    </div>
                  </div>
                </button>
              ))
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
