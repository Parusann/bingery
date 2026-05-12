import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

declare global {
  interface Window {
    LiquidGL?: {
      init: (opts: {
        container: HTMLElement;
        refraction?: number;
        dispersion?: number;
        blur?: number;
        tint?: string;
      }) => { destroy: () => void };
    };
  }
}

interface Props {
  children: ReactNode;
  refraction?: number;
  dispersion?: number;
  blur?: number;
  tint?: string;
  className?: string;
  fallbackClassName?: string;
}

let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.LiquidGL) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/vendor/liquidgl.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("liquidgl failed to load"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export function LiquidGLSurface({
  children,
  refraction = 0.04,
  dispersion = 0.015,
  blur = 6,
  tint = "rgba(255,255,255,0.02)",
  className,
  fallbackClassName,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let cancelled = false;
    const prefersReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;

    loadScript()
      .then(() => {
        if (cancelled || !ref.current || !window.LiquidGL) return;
        const instance = window.LiquidGL.init({
          container: ref.current,
          refraction,
          dispersion,
          blur,
          tint,
        });
        cleanup = () => instance.destroy();
      })
      .catch(() => {
        /* fallback stays visible */
      });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [refraction, dispersion, blur, tint]);

  return (
    <div
      ref={ref}
      className={cn(
        "relative rounded-xl border border-border glass-edge",
        "bg-surface-strong backdrop-blur-xl",
        fallbackClassName,
        className
      )}
    >
      {children}
    </div>
  );
}
