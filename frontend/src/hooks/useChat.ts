import { useState } from "react";
import { api } from "@/lib/api";
import type {
  ChatAnimeRef,
  ChatMessage,
  ChatRole,
} from "@/types/models";

type Mode = "recommend" | "rate" | "onboard";

interface TurnExtra {
  anime?: ChatAnimeRef[];
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
      setTurns((curr) => [
        ...curr,
        {
          role: "assistant",
          content: res.response,
          extra: res.suggested_anime ? { anime: res.suggested_anime } : undefined,
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
