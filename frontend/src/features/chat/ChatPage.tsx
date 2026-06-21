import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { cn } from "@/lib/cn";
import { useChat } from "@/hooks/useChat";
import type { Turn } from "@/hooks/useChat";
import { ChatAnimeCard } from "./ChatAnimeCard";

type Mode = "recommend" | "rate" | "onboard";

const MODE_META: Record<Mode, { label: string; eyebrow: string; seed: Turn[] }> = {
  recommend: {
    label: "Recommend",
    eyebrow: "Get a pick that fits your mood",
    seed: [
      {
        role: "assistant",
        content:
          "Hey — I'm your anime guide. Tell me what you're in the mood for and I'll pick a few.",
      },
    ],
  },
  rate: {
    label: "Rate with AI",
    eyebrow: "Talk through a rating with the AI",
    seed: [
      {
        role: "assistant",
        content:
          "Which anime did you just finish? Tell me how it felt and I'll suggest a score.",
      },
    ],
  },
  onboard: {
    label: "Onboard",
    eyebrow: "Build your taste profile in a few questions",
    seed: [
      {
        role: "assistant",
        content:
          "Let's build your taste. Name three anime you already love and a couple you bounced off.",
      },
    ],
  },
};

export function ChatPage() {
  const [params] = useSearchParams();
  const initialMode = (params.get("mode") as Mode) || "recommend";
  const [mode, setMode] = useState<Mode>(initialMode);
  const { turns, send, loading, error, offline } = useChat(mode, MODE_META[mode].seed);
  const [input, setInput] = useState("");
  const scroller = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scroller.current?.scrollTo({
      top: scroller.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length, loading]);

  return (
    <div className="max-w-4xl mx-auto">
      {/* ─── Header ──────────────────────────────────────────────── */}
      <header className="flex flex-col gap-3 mb-6">
        <div className="flex items-end gap-3 flex-wrap">
          <h1 className="font-display text-4xl md:text-5xl text-amber leading-none flex items-center gap-2.5">
            <span
              aria-hidden
              className="inline-block w-2 h-2 rounded-full bg-amber shadow-[0_0_12px_rgba(244,182,144,0.7)]"
            />
            Guide
          </h1>
          <span className="text-sm text-text-muted mb-1">
            {MODE_META[mode].eyebrow}
          </span>
          <div className="ml-auto flex flex-wrap gap-1.5 md:flex-nowrap">
            {(Object.keys(MODE_META) as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "px-3.5 py-1.5 rounded-pill text-xs font-mono tracking-wider uppercase transition-all",
                  mode === m
                    ? "bg-amber/15 text-amber border border-amber/55"
                    : "text-text-muted border border-border hover:border-border-strong hover:text-text"
                )}
              >
                {MODE_META[m].label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ─── Chat surface ────────────────────────────────────────── */}
      <GlassCard tone="warm" elevated className="overflow-hidden">
        <div
          ref={scroller}
          className="h-[55dvh] md:h-[68vh] overflow-y-auto px-5 md:px-7 py-6 space-y-5"
        >
          <AnimatePresence initial={false}>
            {turns.map((t, i) => {
              const isLatestAssistant =
                t.role === "assistant" && i === turns.length - 1 && !loading;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                  className={cn(
                    "flex",
                    t.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[88%] md:max-w-[78%] flex flex-col gap-3",
                      t.role === "user" ? "items-end" : "items-start"
                    )}
                  >
                    <Bubble role={t.role}>{t.content}</Bubble>
                    {isLatestAssistant && t.extra?.actions?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {t.extra.actions.map((opt, j) => (
                          <motion.button
                            key={opt + j}
                            type="button"
                            onClick={() => {
                              if (!loading) send(opt);
                            }}
                            disabled={loading}
                            initial={{ opacity: 0, y: 4 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.05 * j, duration: 0.2 }}
                            className={cn(
                              "px-4 py-1.5 rounded-pill text-xs font-mono tracking-wider uppercase",
                              "bg-white/[0.04] border border-amber/40 text-amber backdrop-blur-md",
                              "hover:bg-amber/[0.12] hover:border-amber/70 hover:-translate-y-px",
                              "disabled:opacity-40 disabled:hover:translate-y-0 transition-all"
                            )}
                          >
                            {opt}
                          </motion.button>
                        ))}
                      </div>
                    ) : null}
                    {t.role === "assistant" && t.extra?.anime?.length ? (
                      <div className="grid sm:grid-cols-2 gap-2.5 w-full">
                        {t.extra.anime.slice(0, 6).map((a, j) => (
                          <motion.div
                            key={`${a.id ?? j}`}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.08 * j, duration: 0.25 }}
                          >
                            <ChatAnimeCard anime={a} />
                          </motion.div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
          {loading ? (
            <div className="flex justify-start">
              <Bubble role="assistant" muted>
                <span className="inline-flex items-center gap-1.5">
                  <Dot delay={0} />
                  <Dot delay={120} />
                  <Dot delay={240} />
                </span>
              </Bubble>
            </div>
          ) : null}
        </div>

        {/* ─── Composer ────────────────────────────────────────── */}
        <form
          className="flex items-center gap-3 p-4 border-t border-border bg-bg/30 backdrop-blur-md"
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading && input.trim()) {
              send(input);
              setInput("");
            }
          }}
        >
          <input
            type="text"
            placeholder="Tell me what you're in the mood for…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            className="flex-1 h-11 px-5 rounded-pill bg-white/[0.04] border border-amber/30 backdrop-blur-md text-sm placeholder:text-text-dim focus:outline-none focus:border-amber/60 focus:bg-amber/[0.04] transition-colors disabled:opacity-50"
          />
          <Button type="submit" loading={loading} disabled={!input.trim()}>
            Send
          </Button>
        </form>
      </GlassCard>

      {offline ? (
        <div
          className="mt-3 rounded-lg border border-amber/40 bg-amber/[0.06] px-4 py-3 flex items-start gap-3"
          role="status"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-5 h-5 mt-0.5 text-amber shrink-0"
          >
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
          <div className="text-sm leading-snug">
            <div className="font-medium text-text">Taste guide is offline</div>
            <div className="text-text-muted mt-0.5">{error}</div>
          </div>
        </div>
      ) : error ? (
        <p className="mt-3 text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────

function Bubble({
  role,
  children,
  muted,
}: {
  role: Turn["role"];
  children: React.ReactNode;
  muted?: boolean;
}) {
  // Lightweight inline markdown: **bold** and *italic*. We only render this
  // on string children; React node children pass through untouched (used for
  // the dot-typing indicator).
  const content =
    typeof children === "string" ? <Markdown text={children} /> : children;

  if (role === "user") {
    return (
      <div
        className={cn(
          "px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed",
          "bg-gradient-to-b from-amber/[0.22] to-amber/[0.08]",
          "border border-amber/45 text-text shadow-[inset_0_1px_0_rgba(255,220,200,0.18)]"
        )}
      >
        {content}
      </div>
    );
  }
  return (
    <div
      className={cn(
        "relative pl-4 pr-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed",
        "bg-white/[0.035] border border-border backdrop-blur-md",
        muted && "text-text-muted"
      )}
    >
      <span
        aria-hidden
        className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r-sm bg-gradient-to-b from-amber to-amber/30"
      />
      <span className="block whitespace-pre-wrap">{content}</span>
    </div>
  );
}

// Tiny inline markdown renderer — supports **bold** and *italic* on a single
// line. Multi-line content is preserved by the surrounding `whitespace-pre-wrap`.
function Markdown({ text }: { text: string }) {
  // Split on bold or italic spans, capturing the delimiters too.
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
          return (
            <strong key={i} className="font-display text-amber not-italic">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
          return (
            <em key={i} className="italic text-text">
              {part.slice(1, -1)}
            </em>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}
