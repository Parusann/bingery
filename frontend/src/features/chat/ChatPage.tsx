import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { cn } from "@/lib/cn";
import { transitions } from "@/design/motion";
import { useChat } from "@/hooks/useChat";
import type { Turn } from "@/hooks/useChat";
import { ChatAnimeCard } from "./ChatAnimeCard";

const SEED: Turn[] = [
  {
    role: "assistant",
    content:
      "Hey — I'm your anime guide. Name a show you loved or a mood you're in and I'll pick a few.",
  },
];

export function ChatPage() {
  const { turns, send, loading, error, offline } = useChat(SEED);
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
      <header className="flex flex-col gap-1 mb-6">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block w-1.5 h-1.5 rounded-full bg-amber shadow-[0_0_12px_rgba(239,171,129,0.7)]"
          />
          <span className="font-mono text-micro uppercase text-amber">
            AI guide
          </span>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <h1 className="font-display text-display leading-none">Guide</h1>
          <span className="text-sm text-text-muted mb-1">
            Recommendations that fit your taste
          </span>
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
                  transition={transitions.ease}
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
                            transition={{ delay: 0.05 * j, ...transitions.easeFast }}
                            className={cn(
                              "px-4 py-1.5 min-h-[36px] rounded-pill text-micro font-mono uppercase",
                              "bg-surface border border-amber/40 text-amber backdrop-blur-md",
                              "hover:bg-amber/[0.12] hover:border-amber/70 hover:-translate-y-px",
                              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
                              "disabled:opacity-40 disabled:hover:translate-y-0 transition-all"
                            )}
                          >
                            {opt}
                          </motion.button>
                        ))}
                      </div>
                    ) : null}
                    {t.role === "assistant" && t.extra?.seed ? (
                      <motion.div
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={transitions.ease}
                        className="w-full"
                      >
                        <div className="font-mono text-micro uppercase text-amber mb-1.5">
                          Similar to
                        </div>
                        <div className="sm:max-w-[calc(50%-0.3125rem)] rounded-lg shadow-glow-amber">
                          <ChatAnimeCard anime={t.extra.seed} />
                        </div>
                      </motion.div>
                    ) : null}
                    {t.role === "assistant" && t.extra?.anime?.length ? (
                      <div className="grid sm:grid-cols-2 gap-2.5 w-full">
                        {t.extra.anime.slice(0, 6).map((a, j) => (
                          <motion.div
                            key={`${a.id ?? j}`}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.08 * j, ...transitions.ease }}
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
                <TypingIndicator />
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
            className={cn(
              "flex-1 h-11 px-5 rounded-pill text-sm",
              "bg-surface border border-amber/35 backdrop-blur-md",
              "placeholder:text-text-dim transition-colors",
              "focus:outline-none focus:border-amber/60 focus:ring-1 focus:ring-amber/35 focus:bg-amber/[0.04]",
              "disabled:opacity-50"
            )}
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
  // the typing indicator).
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
        "bg-surface border border-border backdrop-blur-md",
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
            <strong key={i} className="font-semibold text-amber-hi">
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

// Signature loading state: three staggered dots + a quiet mono caption.
// framer-motion respects MotionConfig reducedMotion="user" automatically.
function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="inline-flex items-center gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="inline-block w-1.5 h-1.5 rounded-full bg-amber"
            animate={{ y: [0, -3, 0], opacity: [0.4, 1, 0.4] }}
            transition={{
              duration: 0.9,
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </span>
      <span className="font-mono text-micro uppercase text-text-dim">
        Guide is thinking
      </span>
    </span>
  );
}
