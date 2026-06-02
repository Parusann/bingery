import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Leaf, Library, BarChart3, Activity, Scale, MessageCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/design/Button";
import { transitions } from "@/design/motion";
import { useAuth } from "@/stores/auth";
import { useNsfw } from "@/stores/nsfw";
import { NsfwToggle } from "./NsfwToggle";

const DESTINATIONS: { to: string; label: string; Icon: LucideIcon }[] = [
  { to: "/seasonal", label: "Seasonal", Icon: Leaf },
  { to: "/collections", label: "Collections", Icon: Library },
  { to: "/stats", label: "Stats", Icon: BarChart3 },
  { to: "/activity", label: "Activity", Icon: Activity },
  { to: "/compare", label: "Compare", Icon: Scale },
  { to: "/chat", label: "Chat", Icon: MessageCircle },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Bottom sheet of secondary destinations + account controls. Mobile-only.
 * Enter: slide up with transitions.spring; drag-to-dismiss past ~96px.
 *
 * Destination layout: 3-column grid of tiles (shipping default).
 * (Alternative explored in design — full-width list rows: swap the grid for
 *  a `flex flex-col gap-1.5` of `min-h-[56px]` rows with icon + label +
 *  ChevronRight.)
 */
export function MoreSheet({ open, onClose }: Props) {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const nsfwVisible = useNsfw((s) => s.visible);
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape to close + lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  const go = (to: string) => {
    navigate(to);
    onClose();
  };

  return (
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transitions.easeFast}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label="More"
            tabIndex={-1}
            className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-bg-elevated border-t border-border glass-edge outline-none"
            style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={transitions.spring}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.5 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 96) onClose();
            }}
          >
            {/* grab handle */}
            <div className="my-3 flex justify-center">
              <div className="w-9 h-1 rounded-full bg-border-strong" />
            </div>

            {/* destinations */}
            <div className="grid grid-cols-3 gap-2 p-4 pt-0">
              {DESTINATIONS.map(({ to, label, Icon }) => (
                <button
                  key={to}
                  type="button"
                  onClick={() => go(to)}
                  className="flex flex-col items-center justify-center gap-1.5 min-h-[76px] rounded-lg border border-border bg-surface glass-edge backdrop-blur-md text-text-muted hover:text-amber hover:border-amber/40 transition-colors"
                >
                  <Icon size={22} strokeWidth={1.8} />
                  <span className="text-xs">{label}</span>
                </button>
              ))}
            </div>

            <div className="mx-4 border-t border-border" />

            {/* account block */}
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-3">
                {user ? (
                  <>
                    <span className="flex-1 text-text">{user.display_name ?? user.username}</span>
                    <Button variant="ghost" size="sm" onClick={signOut}>
                      Sign out
                    </Button>
                  </>
                ) : (
                  <>
                    <span className="flex-1 text-text-muted text-sm">You&apos;re signed out</span>
                    <Button size="sm" onClick={() => go("/auth")}>
                      Sign in
                    </Button>
                  </>
                )}
              </div>

              {/* NSFW visibility */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2">
                <NsfwToggle size="lg" />
                <div className="flex-1">
                  <div className="text-sm text-text">NSFW</div>
                </div>
                <span className={`font-mono text-[10px] uppercase tracking-widest ${nsfwVisible ? "text-amber" : "text-text-dim"}`}>
                  {nsfwVisible ? "On" : "Off"}
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}
