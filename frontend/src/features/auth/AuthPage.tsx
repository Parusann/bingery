import { Clapperboard } from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { films } from "@/features/landing/films";
import { AuthForm } from "./AuthForm";
import "./auth.css";

export function pathAfterAuth(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || /[\\\t\r\n]/.test(value) || value.startsWith("//")) {
    return "/discover";
  }
  const target = new URL(value, window.location.origin);
  if (target.origin !== window.location.origin || target.pathname.startsWith("//") || /^\/auth\/*$/i.test(target.pathname)) {
    return "/discover";
  }
  return target.pathname + target.search + target.hash;
}

export function AuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const inviteCode = params.get("invite") ?? undefined;
  const inviteEmail = params.get("email") ?? undefined;
  const film = films[0];
  return (
    <div className="auth-page">
      <figure className="auth-image">
        <img src={film.image} alt={film.alt} width={1920} height={1038} />
        <figcaption>
          <span><Clapperboard size={15} aria-hidden="true" /> Film spotlight</span>
          <strong>{film.title}</strong>
          <a href={`https://www.ghibli.jp/works/${film.gallery}/`}>{film.credit}</a>
        </figcaption>
      </figure>
      <div className="auth-panel">
        <AuthForm
          key={params.toString()}
          onSuccess={() => navigate(pathAfterAuth(location.state?.returnTo), { replace: true })}
          initialEmail={inviteEmail}
          initialInviteCode={inviteCode}
          initialMode={params.get("mode") === "waitlist" ? "waitlist" : "login"}
        />
      </div>
    </div>
  );
}
