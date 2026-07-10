import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Collection } from "@/types/models";
import { Button } from "@/design/Button";
import { Input } from "@/design/Input";
import { cn } from "@/lib/cn";
import {
  useCreateCollection,
  useUpdateCollection,
} from "@/hooks/useCollections";

interface Props {
  initial?: Collection;
  onSuccess?: (c: Collection) => void;
}

export function CollectionForm({ initial, onSuccess }: Props) {
  const nav = useNavigate();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isPublic, setIsPublic] = useState(initial?.is_public ?? false);
  const create = useCreateCollection();
  const update = useUpdateCollection(initial?.id ?? -1);
  const busy = create.isPending || update.isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = {
          name: name.trim(),
          description: description.trim() || undefined,
          is_public: isPublic,
        };
        try {
          if (initial) {
            const r = await update.mutateAsync(body);
            onSuccess?.(r.collection);
          } else {
            const r = await create.mutateAsync(body);
            onSuccess?.(r.collection);
            nav(`/collections/${r.collection.id}`);
          }
        } catch {
          /* handled in ui via mutation error state */
        }
      }}
    >
      <Input
        label="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-caption font-medium text-text-muted">
          Description
        </span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className={cn(
            "min-h-[80px] px-3.5 py-2.5 rounded-lg text-sm",
            "bg-surface border border-border outline-none transition-colors",
            "focus:border-amber/50 focus:ring-1 focus:ring-amber/35 focus:bg-amber/[0.03]"
          )}
        />
      </label>
      <label className="flex items-center gap-2.5 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={isPublic}
          onChange={(e) => setIsPublic(e.target.checked)}
          className="w-4 h-4 accent-amber"
        />
        <span className="text-text-muted">
          Public — anyone with the share link can view
        </span>
      </label>
      <div className="flex gap-3 items-center">
        <Button type="submit" loading={busy} disabled={!name.trim()}>
          {initial ? "Save changes" : "Create collection"}
        </Button>
        {create.isError || update.isError ? (
          <span className="text-sm text-danger">
            {(create.error || update.error)?.message}
          </span>
        ) : null}
      </div>
    </form>
  );
}
