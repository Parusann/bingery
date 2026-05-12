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
    return (
      <div className="space-y-4">
        <Skeleton className="h-16" rounded="lg" />
        <Skeleton className="h-64" rounded="lg" />
      </div>
    );
  }
  const c = data.collection;
  const isOwner = user?.id === c.owner_id;

  return (
    <article>
      <header className="flex flex-col gap-3 mb-6">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="font-display text-4xl text-amber">{c.title}</h1>
          <span className="text-sm text-text-muted">
            by {c.owner.display_name ?? c.owner.username}
          </span>
          <div className="ml-auto flex gap-2">
            <ShareButton token={c.share_token} />
            {isOwner ? (
              <>
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
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
        <GlassCard className="p-10 text-center text-text-muted">
          This collection is empty.{" "}
          {isOwner
            ? "Add anime from the discover or detail page."
            : "Nothing here yet."}
        </GlassCard>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {c.items.map((it, i) => (
            <div key={it.id} className="relative group">
              <AnimeCard anime={it.anime} index={i} />
              {isOwner ? (
                <button
                  onClick={() => remove.mutate(it.anime.id)}
                  className="absolute top-2 left-2 px-2 py-0.5 text-xs rounded-md bg-black/60 text-danger opacity-0 group-hover:opacity-100 transition-opacity"
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
          <h2 className="font-display text-2xl mb-4">Edit collection</h2>
          <CollectionForm initial={c} onSuccess={() => setEditing(false)} />
        </div>
      </Modal>
    </article>
  );
}
