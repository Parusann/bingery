import { useNavigate } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { AuthForm } from "./AuthForm";

export function AuthPage() {
  const navigate = useNavigate();
  return (
    <div className="max-w-md mx-auto mt-8">
      <GlassCard tone="warm" className="p-8" elevated>
        <h1 className="font-display text-3xl mb-1">Welcome back</h1>
        <p className="text-text-muted mb-6">
          Sign in to rate, collect, and chat with your taste guide.
        </p>
        <AuthForm onSuccess={() => navigate("/discover")} />
      </GlassCard>
    </div>
  );
}
