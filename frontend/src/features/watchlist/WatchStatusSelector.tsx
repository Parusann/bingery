import { useState } from "react";
import type { WatchStatus } from "@/types/models";
import { Button } from "@/design/Button";
import { STATUSES } from "./StatusTabs";
import {
  useRemoveFromWatchlist,
  useSetWatchStatus,
  useToggleFavorite,
} from "@/hooks/useWatchlist";

interface Props {
  animeId: number;
  current: WatchStatus | null;
  isFavorite: boolean;
}

export function WatchStatusSelector({ animeId, current, isFavorite }: Props) {
  const [open, setOpen] = useState(false);
  const setStatus = useSetWatchStatus();
  const toggleFav = useToggleFavorite();
  const remove = useRemoveFromWatchlist();

  const curMeta = STATUSES.find((s) => s.key === current);

  return (
    <div className="relative inline-flex items-center gap-2">
      <Button
        size="sm"
        variant={current ? "glass" : "primary"}
        onClick={() => setOpen((o) => !o)}
      >
        {curMeta?.label ?? "Add to watchlist"}
      </Button>
      <Button
        size="sm"
        variant={isFavorite ? "primary" : "ghost"}
        onClick={() => toggleFav.mutate(animeId)}
        aria-label="Favorite"
      >
        {isFavorite ? "★" : "☆"}
      </Button>
      {open ? (
        <div className="absolute top-full mt-2 left-0 z-10 flex flex-col gap-1 p-2 rounded-lg bg-bg-elevated border border-border glass-edge min-w-[180px]">
          {STATUSES.map((s) => (
            <button
              key={s.key}
              onClick={() => {
                setStatus.mutate({ animeId, status: s.key });
                setOpen(false);
              }}
              className="text-left text-sm px-3 py-2 rounded-md hover:bg-white/[0.05]"
              style={{ color: s.color }}
            >
              {s.label}
            </button>
          ))}
          {current ? (
            <button
              onClick={() => {
                remove.mutate(animeId);
                setOpen(false);
              }}
              className="text-left text-sm px-3 py-2 rounded-md hover:bg-white/[0.05] text-danger"
            >
              Remove from list
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
