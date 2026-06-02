import { useEffect, useState } from "react";

/**
 * Returns true at >=768px (Tailwind `md`). Used to branch framer-motion
 * variants that can't be expressed with responsive class names alone
 * (e.g. the responsive Modal -> bottom-sheet in @/design/Modal).
 */
export function useIsDesktop(): boolean {
  const query = "(min-width: 768px)";
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setIsDesktop(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return isDesktop;
}
