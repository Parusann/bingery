import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { transitions } from "./motion";
import { useIsDesktop } from "@/lib/useIsDesktop";

interface Props {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  maxWidth?: string;
  className?: string;
}

/**
 * Responsive modal.
 *  - >=768px (md): UNCHANGED from the original — centered dialog, scale/y
 *    enter, max-w via `maxWidth`, max-h-[92vh].
 *  - <768px: docks to the bottom as a native sheet — full width,
 *    rounded-t-2xl, max-h-[85vh], grab handle, slide-up enter,
 *    safe-area bottom padding.
 *
 * Every existing <Modal> consumer (CollectionForm, AddToCollection,
 * AnimePicker, …) is upgraded automatically; no per-consumer changes.
 */
export function Modal({ open, onClose, children, maxWidth = "640px", className }: Props) {
  const isDesktop = useIsDesktop();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Desktop variant values are byte-identical to the original component.
  const panelMotion = isDesktop
    ? {
        initial: { opacity: 0, scale: 0.96, y: 8 },
        animate: { opacity: 1, scale: 1, y: 0 },
        exit: { opacity: 0, scale: 0.96, y: 8 },
      }
    : {
        initial: { y: "100%" },
        animate: { y: 0 },
        exit: { y: "100%" },
      };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center p-0 md:items-center md:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={transitions.easeFast}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className={cn(
              "relative z-10 w-full bg-bg-elevated border border-border glass-edge overflow-y-auto",
              // mobile: bottom sheet
              "rounded-t-2xl max-h-[85vh]",
              // desktop: unchanged centered dialog
              "md:rounded-xl md:max-h-[92vh]",
              className
            )}
            style={{ maxWidth, paddingBottom: isDesktop ? undefined : "env(safe-area-inset-bottom)" }}
            initial={panelMotion.initial}
            animate={panelMotion.animate}
            exit={panelMotion.exit}
            transition={transitions.spring}
            role="dialog"
            aria-modal="true"
          >
            {/* grab handle — mobile only */}
            <div className="md:hidden pt-3 pb-1 flex justify-center sticky top-0">
              <div className="w-9 h-1 rounded-full bg-border-strong" />
            </div>
            {children}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
