import { useState } from "react";
import { Check, Plus } from "lucide-react";
import { Button } from "@/design/Button";
import { Input } from "@/design/Input";
import { Modal } from "@/design/Modal";
import { useAddToCollection, useCollections, useCreateCollection } from "@/hooks/useCollections";

export function AddToCollection({ animeId }: { animeId: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>Add to collection</Button>
      <Modal open={open} onClose={() => setOpen(false)} label="Add to collection" maxWidth="460px">
        <CollectionPicker animeId={animeId} />
      </Modal>
    </>
  );
}

function CollectionPicker({ animeId }: { animeId: number }) {
  const lists = useCollections();
  const create = useCreateCollection();
  const add = useAddToCollection();
  const [newTitle, setNewTitle] = useState("");
  const [added, setAdded] = useState<number[]>([]);
  const busy = create.isPending || add.isPending;
  function save(id: number) {
    add.mutate({ id, animeId }, { onSuccess: () => setAdded((prev) => [...prev, id]) });
  }

  return (
    <div className="p-5 md:p-7">
      <h2 className="font-display text-2xl mb-4">Add to collection</h2>
      {lists.isLoading && <p role="status">Loading collections…</p>}
      {lists.isError && <button type="button" className="text-amber" onClick={() => lists.refetch()}>Collections couldn’t load. Try again</button>}
      {lists.data?.collections.length === 0 && <p className="text-text-muted">Create your first collection below.</p>}
      <div className="space-y-1 max-h-56 overflow-auto">
        {lists.data?.collections.map((c) => (
          <button key={c.id} type="button" onClick={() => save(c.id)}
            className="flex items-center w-full gap-3 rounded-md px-3 py-2 text-left hover:bg-surface-strong disabled:opacity-70"
            disabled={busy || added.includes(c.id)}>
            <span className="flex-1 truncate">{c.name}</span>
            {added.includes(c.id) ? <><Check size={15} /> Added</> : <Plus size={16} />}
          </button>
        ))}
      </div>
      <form className="mt-4 border-t border-border pt-4 space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!newTitle.trim() || busy) return;
          create.mutate({ name: newTitle.trim() }, { onSuccess: ({ collection }) => {
            setNewTitle("");
            save(collection.id);
          } });
        }}>
        <Input label="New collection name" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} maxLength={80} />
        <Button type="submit" size="sm" disabled={!newTitle.trim() || busy}>Create and add</Button>
      </form>
      {(create.isError || add.isError) && <p role="alert" className="mt-3 text-sm text-danger">{(create.error || add.error)?.message}</p>}
      {added.length > 0 && <span role="status" className="sr-only">Added to collection</span>}
    </div>
  );
}
