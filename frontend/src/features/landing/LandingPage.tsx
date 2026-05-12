import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Button } from "@/design/Button";
import { fadeInUp, transitions } from "@/design/motion";

export function LandingPage() {
  return (
    <section className="flex flex-col items-center text-center gap-10 py-16">
      <motion.div
        variants={fadeInUp}
        initial="hidden"
        animate="show"
        transition={transitions.easeSlow}
        className="flex flex-col items-center gap-5 max-w-2xl"
      >
        <span className="text-xs tracking-[0.3em] text-amber uppercase font-mono">
          Anime, quietly curated
        </span>
        <h1 className="font-display text-6xl md:text-7xl leading-[1.02]">
          Discover what you’ll
          <span className="block italic text-amber">actually love.</span>
        </h1>
        <p className="text-text-muted max-w-xl">
          A dark, unhurried space to rate, collect, and find your next favorite
          series — backed by a taste model that listens.
        </p>
        <div className="flex gap-3">
          <Link to="/discover">
            <Button size="lg">Start browsing</Button>
          </Link>
          <Link to="/chat">
            <Button size="lg" variant="ghost">
              Ask the guide
            </Button>
          </Link>
        </div>
      </motion.div>

      <motion.div
        variants={fadeInUp}
        initial="hidden"
        animate="show"
        transition={{ ...transitions.easeSlow, delay: 0.15 }}
        className="w-full max-w-5xl"
      >
        <LiquidGLSurface className="p-8 md:p-12">
          <div className="grid md:grid-cols-3 gap-6 text-left">
            <Feature
              title="Rate"
              body="Ten-point ratings with optional reviews and fan-genre votes."
            />
            <Feature
              title="Track"
              body="Watching, plan to watch, on hold, dropped — or keep it private."
            />
            <Feature
              title="Find"
              body="A Claude or local-model guide tuned to your taste."
            />
          </div>
        </LiquidGLSurface>
      </motion.div>
    </section>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="font-display text-2xl text-amber mb-2">{title}</h3>
      <p className="text-text-muted">{body}</p>
    </div>
  );
}
