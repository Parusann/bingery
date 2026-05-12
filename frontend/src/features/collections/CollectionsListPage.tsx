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
        <h1 className="font-display text-4xl mb-2">Sign in to build collections</h1>
        <p className="text-text-muted">
          Organize anime into private or shareable lists.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h1 className="font-display text-4xl text-amber">Collections</h1>
        <Button className="ml-auto" onClick={() => setCreating(true)}>
          New collection
        </Button>
      </div>
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48" rounded="lg" />
          ))}
        </div>
      ) : data && data.collections.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.collections.map((c, i) => (
            <CollectionCard key={c.id} collection={c} index={i} />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center text-text-muted">
          No collections yet. Start one above.
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)}>
        <div className="p-6">
          <h2 className="font-display text-2xl mb-4">New collection</h2>
          <CollectionForm onSuccess={() => setCreating(false)} />
        </div>
      </Modal>
    </div>
  );
}
