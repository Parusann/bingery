import { useState } from "react";
import { Button } from "@/design/Button";

export function ShareButton({ token }: { token: string | null }) {
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [manualToken, setManualToken] = useState<string | null>(null);
  if (!token) return null;
  const url = new URL("/collections/share/" + encodeURIComponent(token), window.location.origin).href;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="ghost" onClick={async () => {
        try {
          await navigator.clipboard.writeText(url);
          setCopiedToken(token);
          setManualToken(null);
        } catch {
          setManualToken(token);
        }
      }}>
        {copiedToken === token ? "Link copied" : "Copy share link"}
      </Button>
      {manualToken === token &&
        <label className="text-xs text-text-muted">Copy this link
          <input autoFocus readOnly value={url} onFocus={(event) => event.target.select()}
            className="block mt-1 w-full rounded-md bg-surface px-2 py-1 text-text" />
        </label>}
    </div>
  );
}
