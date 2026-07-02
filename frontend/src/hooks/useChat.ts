import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  ChatAnimeRef,
  ChatMessage,
  ChatRole,
} from "@/types/models";

interface TurnExtra {
  anime?: ChatAnimeRef[];
  actions?: string[];
}

interface Turn {
  role: ChatRole;
  content: string;
  extra?: TurnExtra;
}

export function useChat(seed: Turn[] = []) {
  const [turns, setTurns] = useState<Turn[]>(seed);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  async function send(userText: string) {
    if (!userText.trim()) return;
    const next: Turn[] = [...turns, { role: "user", content: userText }];
    setTurns(next);
    setLoading(true);
    setError(null);
    setOffline(false);
    try {
      const conversation: ChatMessage[] = next.map((t) => ({
        role: t.role,
        content: t.content,
      }));
      const res = await api.chatMessage({
        message: userText,
        conversation,
        mode: "recommend",
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
      if (
        e instanceof ApiError &&
        e.status === 503 &&
        e.code === "provider_unavailable"
      ) {
        setOffline(true);
      }
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return { turns, setTurns, send, loading, error, offline };
}

export type { Turn };
