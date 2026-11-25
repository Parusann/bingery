import { useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  ChatAnimeRef,
  ChatMessage,
  ChatRole,
} from "@/types/models";

interface TurnExtra {
  anime?: ChatAnimeRef[];
  actions?: string[];
  seed?: ChatAnimeRef;
}

interface Turn {
  role: ChatRole;
  content: string;
  extra?: TurnExtra;
  failed?: boolean;
}

export function useChat(seed: Turn[] = []) {
  const [turns, setTurns] = useState<Turn[]>(seed);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  const sending = useRef(false);

  async function requestReply(userText: string, prior: Turn[]) {
    const message = userText.trim();
    if (sending.current || !message) return;
    sending.current = true;
    const userTurn: Turn = { role: "user", content: message };
    setTurns([...prior, userTurn]);
    setLoading(true);
    setError(null);
    setOffline(false);
    try {
      // Flask appends the current message. Only send completed history here.
      const conversation: ChatMessage[] = prior.slice(seed.length)
        .filter((turn) => !turn.failed)
        .map(({ role, content }) => ({ role, content }));
      const res = await api.chatMessage({
        message,
        conversation,
        mode: "recommend",
      });
      const hasAnime = !!res.suggested_anime?.length;
      const hasActions = !!res.suggested_actions?.length;
      const hasSeed = !!res.seed_anime;
      setTurns((curr) => [
        ...curr,
        {
          role: "assistant",
          content: res.response,
          extra: hasAnime || hasActions || hasSeed
            ? {
                anime: hasAnime ? res.suggested_anime : undefined,
                actions: hasActions ? res.suggested_actions : undefined,
                seed: hasSeed ? res.seed_anime ?? undefined : undefined,
              }
            : undefined,
        },
      ]);
    } catch (e) {
      setTurns([...prior, { ...userTurn, failed: true }]);
      if (
        e instanceof ApiError &&
        e.status === 503 &&
        e.code === "provider_unavailable"
      ) {
        setOffline(true);
      }
      setError((e as Error).message);
    } finally {
      sending.current = false;
      setLoading(false);
    }
  }

  const send = (text: string) => requestReply(text, turns);
  function retry() {
    const last = turns.at(-1);
    if (last?.failed) return requestReply(last.content, turns.slice(0, -1));
  }

  return { turns, send, retry, loading, error, offline };
}

export type { Turn };
