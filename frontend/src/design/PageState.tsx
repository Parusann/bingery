import { ArrowRight, Library } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "./Button";
import { useAuth } from "@/stores/auth";

export function SignInPanel({ title, description, section }: { title: string; description: string; section: string }) {
  const { pathname, search, hash } = useLocation();
  const restoring = useAuth((s) => s.status === "loading");
  if (restoring) return <p role="status" className="py-16 text-center text-text-muted">Loading your account…</p>;
  return (
    <section className="account-gate">
      <div className="flex items-center gap-2 text-sm text-amber"><Library size={18} aria-hidden />{section}</div>
      <h1>{title}</h1>
      <p className="text-text-muted">{description}</p>
      <div className="gate-actions">
        <Link to="/auth" state={{ returnTo: pathname + search + hash }} className="gate-primary">Sign in <ArrowRight size={16} aria-hidden /></Link>
        <Link to="/discover" className="text-sm text-text-muted underline underline-offset-4 hover:text-text">Browse the catalog</Link>
      </div>
    </section>
  );
}

export function LoadError({ title, retry }: { title: string; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-border bg-surface px-5 py-8 text-center">
      <p className="font-display text-xl">{title}</p>
      {retry && <Button className="mt-4" variant="glass" size="sm" onClick={retry}>Try again</Button>}
    </div>
  );
}
