import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  ChatAnimeRef,
  ChatMessage,
  ChatRole,
} from "@/types/models";

type Mode = "recommend" | "rate" | "onboard";

interface TurnExtra {
  anime?: ChatAnimeRef[];
  actions?: string[];
}

interface Turn {
  role: ChatRole;
  content: string;
  extra?: TurnExtra;
}

export function useChat(mode: Mode, seed: Turn[] = []) {
  const [turns, setTurns] = useState<Turn[]>(seed);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // When the mode changes, reset the conversation to that mode's seed so
  // the greeting + system prompt context match what the user sees. Without
  // this, switching to Rate or Onboard still shows the Recommend greeting,
  // and small local models anchor on the old assistant turn and keep
  // recommending titles instead of obeying the new mode prompt.
  const lastMode = useRef(mode);
  useEffect(() => {
    if (lastMode.current === mode) return;
    lastMode.current = mode;
    setTurns(seed);
    setError(null);
    setLoading(false);
  }, [mode, seed]);

  async function send(userText: string) {
    if (!userText.trim()) return;
    const next: Turn[] = [...turns, { role: "user", content: userText }];
    setTurns(next);
    setLoading(true);
    setError(null);
    try {
      const conversation: ChatMessage[] = next.map((t) => ({
        role: t.role,
        content: t.content,
      }));
      const res = await api.chatMessage({
        message: userText,
        conversation,
        mode,
      });
      const hasAnime = !!res.suggested_anime?.length;
      const hasActions = !!res.suggested_actions?.length;
      setTurns((curr) => [
        ...curr,
        {
          role: "assistant",
          content: res.response,
          extra: hasAnime || hasActions
            ? {
                anime: hasAnime ? res.suggested_anime : undefined,
                actions: hasActions ? res.suggested_actions : undefined,
              }
            : undefined,
        },
      ]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return { turns, setTurns, send, loading, error };
}

export type { Turn };
