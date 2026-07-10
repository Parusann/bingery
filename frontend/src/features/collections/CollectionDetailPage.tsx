import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Modal } from "@/design/Modal";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { AnimeCard } from "@/features/discover/AnimeCard";
import { useAuth } from "@/stores/auth";
import {
  useCollection,
  useDeleteCollection,
  useRemoveFromCollection,
} from "@/hooks/useCollections";
import { CollectionForm } from "./CollectionForm";
import { ShareButton } from "./ShareButton";

export function CollectionDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const numericId = id ? Number(id) : undefined;
  const user = useAuth((s) => s.user);
  const { data, isLoading } = useCollection(numericId);
  const del = useDeleteCollection();
  const remove = useRemoveFromCollection(numericId ?? -1);
  const [editing, setEditing] = useState(false);

  if (isLoading || !data) {
    // Mirrors the real page: title row, then a poster grid.
    return (
      <div>
        <div className="flex items-baseline gap-3 mb-6">
          <Skeleton className="h-9 w-64" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[2/3]" rounded="lg" />
          ))}
        </div>
      </div>
    );
  }
  const c = data.collection;
  const isOwner = user?.id === c.user_id;
  const ownerLabel = c.owner
    ? c.owner.display_name ?? c.owner.username
    : null;

  return (
    <article>
      <header className="flex flex-col gap-3 mb-6">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="font-display text-display">{c.name}</h1>
          {ownerLabel ? (
            <span className="text-sm text-text-muted">by {ownerLabel}</span>
          ) : null}
          <div className="ml-auto flex gap-2">
            <ShareButton token={c.share_token} />
            {isOwner ? (
              <>
                <Button size="sm" variant="glass" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={async () => {
                    if (!window.confirm("Delete this collection?")) return;
                    await del.mutateAsync(c.id);
                    nav("/collections");
                  }}
                >
                  Delete
                </Button>
              </>
            ) : null}
          </div>
        </div>
        {c.description ? (
          <p className="text-text-muted max-w-3xl">{c.description}</p>
        ) : null}
      </header>

      {c.items.length === 0 ? (
        <GlassCard className="p-10 text-center">
          <div className="font-mono text-micro uppercase text-text-dim mb-3">
            Empty collection
          </div>
          <p className="font-display italic text-title text-text-muted">
            This collection is empty.{" "}
            {isOwner
              ? "Add anime from the discover or detail page."
              : "Nothing here yet."}
          </p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6">
          {c.items.map((it, i) => (
            <div key={it.id} className="relative group">
              <AnimeCard anime={it.anime} index={i} />
              {isOwner ? (
                <button
                  onClick={() => remove.mutate(it.anime.id)}
                  className="absolute top-2 left-2 px-2 py-1 text-xs rounded-md bg-bg/80 backdrop-blur-md border border-danger/40 text-danger opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity hover:bg-danger/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/60"
                  aria-label="Remove"
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <Modal open={editing} onClose={() => setEditing(false)}>
        <div className="p-6">
          <h2 className="font-display text-title mb-4">Edit collection</h2>
          <CollectionForm initial={c} onSuccess={() => setEditing(false)} />
        </div>
      </Modal>
    </article>
  );
}
