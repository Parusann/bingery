import { useState } from "react";
import { Button } from "@/design/Button";

export function ShareButton({ token }: { token: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!token) return null;
  const url = `${window.location.origin}/collections/share/${token}`;
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={async () => {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Link copied" : "Copy share link"}
    </Button>
  );
}
