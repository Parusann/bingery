import { Input } from "@/design/Input";

interface Props {
  a: string;
  b: string;
  onA: (v: string) => void;
  onB: (v: string) => void;
  onSubmit: () => void;
}

export function UserPicker({ a, b, onA, onB, onSubmit }: Props) {
  return (
    <form
      className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end"
      onSubmit={(e) => {
        e.preventDefault();
        if (a.trim() && b.trim()) onSubmit();
      }}
    >
      <Input label="User A" value={a} onChange={(e) => onA(e.target.value)} />
      <Input label="User B" value={b} onChange={(e) => onB(e.target.value)} />
      <button
        type="submit"
        className="h-10 px-4 rounded-lg bg-amber text-bg font-medium disabled:opacity-50"
        disabled={!a.trim() || !b.trim()}
      >
        Compare
      </button>
    </form>
  );
}
