import { useState } from "react";
import { Button } from "@/design/Button";
import {
  useAddToCollection,
  useCollections,
  useCreateCollection,
} from "@/hooks/useCollections";

interface Props {
  animeId: number;
}

export function AddToCollection({ animeId }: Props) {
  const { data } = useCollections();
  const [open, setOpen] = useState(false);
  const create = useCreateCollection();
  const [newTitle, setNewTitle] = useState("");
  const collections = data?.collections ?? [];

  return (
    <div className="relative">
      <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
        Add to collection
      </Button>
      {open ? (
        <div className="absolute right-0 top-full mt-2 z-10 w-72 rounded-lg border border-border bg-bg-elevated glass-edge p-3 space-y-2">
          {collections.length === 0 ? (
            <p className="text-xs text-text-muted px-1 py-2">
              No collections yet. Create one below.
            </p>
          ) : (
            <div className="max-h-56 overflow-y-auto">
              {collections.map((c) => (
                <AddRow key={c.id} collectionId={c.id} title={c.title} animeId={animeId} />
              ))}
            </div>
          )}
          <form
            className="flex gap-2 pt-2 border-t border-border"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!newTitle.trim()) return;
              const r = await create.mutateAsync({ title: newTitle.trim() });
              setNewTitle("");
              await new Promise((res) => setTimeout(res, 60));
              const item = document.querySelector<HTMLButtonElement>(
                `[data-add-row="${r.collection.id}"]`
              );
              item?.click();
            }}
          >
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="New collection title…"
              className="flex-1 h-8 px-2 rounded-md bg-surface border border-border text-sm outline-none"
            />
            <Button size="sm" type="submit" disabled={!newTitle.trim()}>
              Add
            </Button>
          </form>
        </div>
      ) : null}
    </div>
  );
}

function AddRow({
  collectionId,
  title,
  animeId,
}: {
  collectionId: number;
  title: string;
  animeId: number;
}) {
  const add = useAddToCollection(collectionId);
  const [done, setDone] = useState(false);
  return (
    <button
      data-add-row={collectionId}
      onClick={async () => {
        try {
          await add.mutateAsync({ anime_id: animeId });
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* toast later */
        }
      }}
      className="w-full text-left text-sm px-2 py-2 rounded-md hover:bg-white/[0.05] flex items-center justify-between"
    >
      <span>{title}</span>
      <span className="text-xs text-text-muted">
        {add.isPending ? "…" : done ? "✓" : "+"}
      </span>
    </button>
  );
}
