import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { transitions } from "./motion";

interface Props {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  maxWidth?: string;
  className?: string;
}

export function Modal({ open, onClose, children, maxWidth = "640px", className }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
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
              "relative z-10 w-full bg-bg-elevated border border-border rounded-xl glass-edge",
              "max-h-[92vh] overflow-y-auto",
              className
            )}
            style={{ maxWidth }}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={transitions.spring}
            role="dialog"
            aria-modal="true"
          >
            {children}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
