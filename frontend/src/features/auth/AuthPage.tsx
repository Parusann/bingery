import { useNavigate, useSearchParams } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { AuthForm } from "./AuthForm";

export function AuthPage() {
  const navigate = useNavigate();
  // Invite emails link to /auth?invite=<code>&email=<address>.
  const [params] = useSearchParams();
  const inviteCode = params.get("invite") ?? undefined;
  const inviteEmail = params.get("email") ?? undefined;
  return (
    <div className="max-w-md mx-auto mt-8">
      <GlassCard tone="warm" className="p-8" elevated>
        <div className="font-mono text-micro uppercase text-amber mb-2">
          Bingery
        </div>
        <h1 className="font-display text-title mb-1">Welcome back</h1>
        <p className="text-text-muted mb-6">
          Sign in to rate, collect, and chat with your taste guide.
        </p>
        <AuthForm
          onSuccess={() => navigate("/discover")}
          initialEmail={inviteEmail}
          initialInviteCode={inviteCode}
        />
      </GlassCard>
    </div>
  );
}
