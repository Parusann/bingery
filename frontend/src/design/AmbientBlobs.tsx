import { motion } from "framer-motion";

export function AmbientBlobs() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 overflow-hidden z-0"
    >
      <motion.div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 720,
          height: 720,
          left: "-20%",
          top: "-30%",
          background:
            "radial-gradient(closest-side, rgba(230,166,128,0.45), rgba(230,166,128,0) 70%)",
        }}
        animate={{ x: [0, 40, 0], y: [0, 20, 0] }}
        transition={{ duration: 18, ease: "easeInOut", repeat: Infinity }}
      />
      <motion.div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 640,
          height: 640,
          right: "-15%",
          bottom: "-25%",
          background:
            "radial-gradient(closest-side, rgba(184,154,196,0.30), rgba(184,154,196,0) 70%)",
        }}
        animate={{ x: [0, -30, 0], y: [0, -15, 0] }}
        transition={{ duration: 22, ease: "easeInOut", repeat: Infinity }}
      />
    </div>
  );
}
