import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { SignInPanel, LoadError } from "@/design/PageState";
import { ApiError } from "@/lib/api";
import { Modal } from "@/design/Modal";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { AnimeCard } from "@/features/discover/AnimeCard";
import { useAuth } from "@/stores/auth";
import {
  useCollection,
  useSharedCollection,
  useDeleteCollection,
  useRemoveFromCollection,
} from "@/hooks/useCollections";
import { CollectionForm } from "./CollectionForm";
import { ShareButton } from "./ShareButton";

export function CollectionDetailPage() {
  const { id, token } = useParams();
  const nav = useNavigate();
  const numericId = id && /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? Number(id) : undefined;
  const user = useAuth((s) => s.user);
  const owned = useCollection(user ? numericId : undefined);
  const shared = useSharedCollection(token);
  const query = token ? shared : owned;
  const { data, isLoading } = query;
  const del = useDeleteCollection();
  const remove = useRemoveFromCollection(numericId ?? -1);
  const [editing, setEditing] = useState(false);

  if (!token && !user) return <SignInPanel section="Collections" title="Sign in to see your collection"
    description="Open your saved list to view, edit, or share it." />;
  if ((!token && !numericId) || (query.error instanceof ApiError && query.error.status === 404)) {
    return <div className="account-gate"><h1>Collection unavailable</h1>
      <p className="text-text-muted">This collection may be private, or its share link may have expired.</p>
      <Link to="/discover" className="gate-primary mt-6">Browse anime</Link></div>;
  }
  if (query.isError && !data) return <LoadError title="This collection couldn’t load." retry={() => query.refetch()} />;
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
  const isOwner = !token && !!user && user.id === c.user_id;

  return (
    <article>
      <header className="flex flex-col gap-3 mb-6">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="font-display text-display">{c.name}</h1>
          {token && <span className="text-sm text-text-muted">Shared collection</span>}
          <div className="ml-auto flex gap-2">
            <ShareButton token={token || c.share_token || null} />
            {isOwner ? (
              <>
                <Button size="sm" variant="glass" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  loading={del.isPending}
                  onClick={() => {
                    if (!window.confirm("Delete this collection?")) return;
                    del.mutate(c.id, { onSuccess: () => nav("/collections") });
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

      {(del.isError || remove.isError) && <p role="alert" className="mb-4 text-danger">{(del.error || remove.error)?.message}</p>}
      {c.items.length === 0 ? (
        <GlassCard className="p-10 text-center">
          <div className="font-mono text-micro uppercase text-text-dim mb-3">
            Empty collection
          </div>
          <p className="font-display italic text-title text-text-muted">
            This collection is empty.{" "}
            {isOwner && <Link className="text-amber underline" to="/discover">Browse anime to add a title.</Link>}
          </p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6">
          {c.items.map((it, i) => (
            <div key={it.id} className="relative group">
              {it.anime ? <AnimeCard anime={it.anime} index={i} /> : <p className="p-4 text-text-muted">Title unavailable</p>}
              {isOwner ? (
                <button
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(it.anime_id)}
                  className="absolute top-2 left-2 px-2 py-1 text-xs rounded-md bg-bg/80 backdrop-blur-md border border-danger/40 text-danger md:opacity-0 md:group-hover:opacity-100 focus-visible:opacity-100 transition-opacity hover:bg-danger/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/60"
                  aria-label={`Remove ${it.anime?.title_english || it.anime?.title || "title"} from collection`}
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <Modal label="Edit collection" open={editing} onClose={() => setEditing(false)}>
        <div className="p-6">
          <h2 className="font-display text-title mb-4">Edit collection</h2>
          <CollectionForm initial={c} onSuccess={() => setEditing(false)} />
        </div>
      </Modal>
    </article>
  );
}
