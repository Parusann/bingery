import type { Transition, Variants } from "framer-motion";
import { motion as t } from "./tokens";

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1 },
};

export const pressDown: Variants = {
  rest: { scale: 1 },
  hover: { scale: 1.02 },
  press: { scale: 0.97 },
};

export const transitions: Record<string, Transition> = {
  ease: { duration: t.duration.base, ease: [...t.ease] },
  easeFast: { duration: t.duration.fast, ease: [...t.easeOut] },
  easeSlow: { duration: t.duration.slow, ease: [...t.ease] },
  spring: { ...t.spring.soft },
  springSnappy: { ...t.spring.snappy },
};

export const staggerChildren = (delay = 0.04): Transition => ({
  staggerChildren: delay,
});
