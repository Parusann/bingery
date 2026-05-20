import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
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
      <div className="rounded-lg border border-border bg-bg-elevated/60 p-3 flex gap-3 items-start">
        {value.image_url ? (
          <img
            src={value.image_url}
            alt=""
            className="w-14 h-20 object-cover rounded"
          />
        ) : (
          <div className="w-14 h-20 rounded bg-white/5" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-1">
            {label}
          </div>
          <div className="font-display text-lg leading-tight line-clamp-2">
            {value.title_english || value.title}
          </div>
          <div className="text-xs text-text-muted mt-1">
            {value.year ?? "—"}
            {value.api_score != null ? ` · ★ ${value.api_score.toFixed(1)}` : ""}
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            onChange(null);
            setQ("");
          }}
          className="text-text-muted hover:text-text px-2 py-1 text-sm rounded hover:bg-white/[0.05]"
          aria-label={`Clear ${label}`}
        >
          ✕
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
            className="absolute left-0 right-0 mt-2 rounded-lg border border-border bg-bg-elevated/95 backdrop-blur-xl overflow-hidden z-20"
          >
            {loading ? (
              <div className="p-3 text-sm text-text-muted">Searching…</div>
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
                  className="flex gap-3 w-full text-left p-2 hover:bg-white/[0.05]"
                >
                  {a.image_url ? (
                    <img
                      src={a.image_url}
                      alt=""
                      className="w-10 h-14 object-cover rounded"
                    />
                  ) : (
                    <div className="w-10 h-14 rounded bg-white/5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium line-clamp-1">
                      {a.title_english || a.title}
                    </div>
                    <div className="text-xs text-text-muted">
                      {a.year ?? "—"}
                      {a.api_score != null
                        ? ` · ★ ${a.api_score.toFixed(1)}`
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
