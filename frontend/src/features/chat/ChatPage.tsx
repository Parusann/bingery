import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Input } from "@/design/Input";
import { cn } from "@/lib/cn";
import { useChat } from "@/hooks/useChat";
import type { Turn } from "@/hooks/useChat";
import { ChatAnimeCard } from "./ChatAnimeCard";

type Mode = "recommend" | "rate" | "onboard";

const SEED: Record<Mode, Turn[]> = {
  recommend: [
    {
      role: "assistant",
      content:
        "Hey — I'm your anime guide. Tell me what you're in the mood for and I'll pick three.",
    },
  ],
  rate: [],
  onboard: [
    {
      role: "assistant",
      content:
        "Let's build your taste profile. Name three anime you already love and a couple you disliked.",
    },
  ],
};

export function ChatPage() {
  const [params] = useSearchParams();
  const initialMode = (params.get("mode") as Mode) || "recommend";
  const [mode, setMode] = useState<Mode>(initialMode);
  const { turns, send, loading, error } = useChat(mode, SEED[mode]);
  const [input, setInput] = useState("");
  const scroller = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scroller.current?.scrollTo({
      top: scroller.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-4">
        <h1 className="font-display text-4xl text-amber">Guide</h1>
        <div className="ml-auto flex gap-1">
          {(["recommend", "rate", "onboard"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm",
                mode === m
                  ? "bg-white/[0.08] text-text"
                  : "text-text-muted hover:text-text"
              )}
            >
              {m === "recommend" ? "Recommend" : m === "rate" ? "Rate with AI" : "Onboard"}
            </button>
          ))}
        </div>
      </div>
      <GlassCard className="h-[60vh] flex flex-col">
        <div ref={scroller} className="flex-1 overflow-y-auto p-5 space-y-4">
          {turns.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "max-w-[85%]",
                t.role === "user" ? "ml-auto" : "mr-auto"
              )}
            >
              <div
                className={cn(
                  "px-4 py-3 rounded-2xl text-sm leading-relaxed",
                  t.role === "user"
                    ? "bg-amber text-bg"
                    : "bg-white/[0.04] border border-border"
                )}
              >
                {t.content}
              </div>
              {t.extra?.anime?.length ? (
                <div className="mt-2 grid gap-2">
                  {t.extra.anime.slice(0, 3).map((a, j) => (
                    <ChatAnimeCard key={j} anime={a} />
                  ))}
                </div>
              ) : null}
            </motion.div>
          ))}
          {loading ? (
            <div className="mr-auto px-4 py-3 rounded-2xl bg-white/[0.04] border border-border text-sm text-text-muted">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse mr-1" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse mr-1 [animation-delay:0.15s]" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse [animation-delay:0.3s]" />
            </div>
          ) : null}
        </div>
        <form
          className="p-3 border-t border-border flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading) {
              send(input);
              setInput("");
            }
          }}
        >
          <Input
            className="flex-1"
            placeholder="Type a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <Button type="submit" loading={loading} disabled={!input.trim()}>
            Send
          </Button>
        </form>
      </GlassCard>
      {error ? (
        <p className="mt-3 text-sm text-danger">{error}</p>
      ) : null}
    </div>
  );
}
