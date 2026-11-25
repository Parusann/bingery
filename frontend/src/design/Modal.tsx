import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

interface Props {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  label: string;
  maxWidth?: string;
  className?: string;
}

export function Modal({ open, onClose, children, label, maxWidth = "640px", className }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const dragStart = useRef<number | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!open || !dialog) return;
    const trigger = document.activeElement;
    dialog.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus({ preventScroll: true });
    };
  }, [open]);

  if (!open) return null;
  return (
    <dialog
      ref={ref}
      aria-label={label}
      className={cn("bingery-dialog", className)}
      style={{ maxWidth }}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
      }}
    >
      <div
        aria-hidden
        className="md:hidden h-5 grid place-items-center touch-none"
        onPointerDown={(event) => {
          dragStart.current = event.clientY;
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerUp={(event) => {
          if (dragStart.current !== null && event.clientY - dragStart.current > 64) onClose();
          dragStart.current = null;
        }}
        onPointerCancel={() => { dragStart.current = null; }}
      ><span className="h-1 w-10 rounded-full bg-border-strong" /></div>
      <button type="button" aria-label="Close dialog" onClick={onClose} className="dialog-close">
        <X aria-hidden size={18} />
      </button>
      {children}
    </dialog>
  );
}
