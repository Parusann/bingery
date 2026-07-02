import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Search } from "lucide-react";
import { Input } from "@/design/Input";
import { useSearch } from "@/hooks/useSearch";
import { transitions } from "@/design/motion";

interface Props {
  onSubmit?: (q: string) => void;
}

export function SearchAutocomplete({ onSubmit }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement | null>(null);
  const { results, loading } = useSearch(q);
  const nav = useNavigate();

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div ref={wrap} className="relative flex-1 max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) {
            setOpen(false);
            onSubmit?.(q.trim());
          }
        }}
      >
        <Input
          placeholder="Search anime…"
          value={q}
          leading={<Search aria-hidden className="w-4 h-4 text-text-dim shrink-0" />}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
        />
      </form>
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
                    setOpen(false);
                    setQ("");
                    nav(`/anime/${a.id}`);
                  }}
                  className="flex gap-3 w-full text-left p-2.5 transition-colors hover:bg-surface-strong"
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
                    <div className="text-sm truncate">
                      {a.title_english ?? a.title}
                    </div>
                    <div className="text-xs text-text-dim truncate tnum">
                      {a.year ?? ""} {a.format ?? ""}
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
