import { useState } from "react";
import { Button } from "@/design/Button";
import { Modal } from "@/design/Modal";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useCollections } from "@/hooks/useCollections";
import { CollectionCard } from "./CollectionCard";
import { CollectionForm } from "./CollectionForm";

export function CollectionsListPage() {
  const user = useAuth((s) => s.user);
  const { data, isLoading } = useCollections();
  const [creating, setCreating] = useState(false);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <div className="font-mono text-micro uppercase text-amber mb-3">
          Collections
        </div>
        <h1 className="font-display text-display mb-2">
          Sign in to build collections
        </h1>
        <p className="text-text-muted">
          Organize anime into private or shareable lists.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-end gap-4 mb-6">
        <div>
          <div className="font-mono text-micro uppercase text-amber mb-2">
            Curation
          </div>
          <h1 className="font-display text-display">Collections</h1>
        </div>
        <Button className="ml-auto" onClick={() => setCreating(true)}>
          New collection
        </Button>
      </div>
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            // Mirrors CollectionCard: cover band + meta row.
            <div key={i} className="rounded-xl border border-border overflow-hidden">
              <Skeleton className="aspect-[5/3]" rounded="sm" />
              <div className="p-3">
                <Skeleton className="h-4 w-2/3" />
              </div>
            </div>
          ))}
        </div>
      ) : data && data.collections.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.collections.map((c, i) => (
            <CollectionCard key={c.id} collection={c} index={i} />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center">
          <div className="font-mono text-micro uppercase text-text-dim mb-3">
            No lists yet
          </div>
          <p className="font-display italic text-title text-text-muted">
            No collections yet. Start one above.
          </p>
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)}>
        <div className="p-6">
          <h2 className="font-display text-title mb-4">New collection</h2>
          <CollectionForm onSuccess={() => setCreating(false)} />
        </div>
      </Modal>
    </div>
  );
}
