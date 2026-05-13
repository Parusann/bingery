import { motion } from "framer-motion";
import { useInView } from "react-intersection-observer";
import type { ReactNode } from "react";
import { transitions } from "./motion";

interface Props {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}

export function ScrollReveal({ children, delay = 0, y = 14, className }: Props) {
  const { ref, inView } = useInView({ threshold: 0.1, triggerOnce: true });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y }}
      transition={{ ...transitions.ease, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
