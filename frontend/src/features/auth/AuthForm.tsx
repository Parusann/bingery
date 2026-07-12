import { useEffect, useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

type Mode = "login" | "register" | "waitlist";
type Step = "form" | "verify";

const RESEND_SECONDS = 60;

interface AuthFormProps {
  onSuccess?: () => void;
  /** Prefill from an invite email link (/auth?invite=<code>&email=<address>). */
  initialEmail?: string;
  initialInviteCode?: string;
}

export function AuthForm({
  onSuccess,
  initialEmail,
  initialInviteCode,
}: AuthFormProps) {
  // An invite link lands straight on the sign-up form with code + email set.
  const [mode, setMode] = useState<Mode>(
    initialInviteCode ? "register" : "login"
  );
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState(initialEmail ?? "");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [inviteCode, setInviteCode] = useState(initialInviteCode ?? "");
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(RESEND_SECONDS);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [waitlistStatus, setWaitlistStatus] = useState<
    "added" | "already" | null
  >(null);
  const signIn = useAuth((s) => s.signIn);
  const signUp = useAuth((s) => s.signUp);
  const verifyEmail = useAuth((s) => s.verifyEmail);
  const resendCode = useAuth((s) => s.resendCode);

  // Resend countdown, ticking only on the verify step.
  useEffect(() => {
    if (step !== "verify" || resendIn <= 0) return;
    const t = setInterval(() => setResendIn((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [step, resendIn]);

  const submit = async () => {
    setError(null);
    setLoading(true);
    try {
      if (mode === "waitlist") {
        const res = await api.joinWaitlist({
          email: email.trim().toLowerCase(),
        });
        setWaitlistStatus(res.status);
      } else if (mode === "login") {
        await signIn({ email, password });
        onSuccess?.();
      } else if (step === "form") {
        const normEmail = email.trim().toLowerCase();
        await signUp({
          email: normEmail,
          password,
          username,
          display_name: displayName.trim() || undefined,
          invite_code: inviteCode.trim() || undefined,
        });
        setEmail(normEmail);
        setCode("");
        setResendIn(RESEND_SECONDS);
        setResent(false);
        setStep("verify");
      } else {
        setResent(false);
        await verifyEmail({ email: email.trim().toLowerCase(), code });
        onSuccess?.();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    if (resending) return;
    setError(null);
    setResending(true);
    try {
      await resendCode({ email: email.trim().toLowerCase() });
      setResendIn(RESEND_SECONDS);
      setResent(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setResending(false);
    }
  };

  if (step === "verify") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex flex-col gap-4"
      >
        <div>
          <h2 className="font-display text-title mb-1">Check your email</h2>
          <p className="text-sm text-text-muted">
            We sent a 6-digit code to <span className="text-text">{email}</span>.
          </p>
        </div>
        <Input
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          className="text-center tracking-[0.4em] font-mono tnum text-lg"
          required
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {resent && !error ? (
          <p className="text-sm text-success">Code sent.</p>
        ) : null}
        <Button type="submit" loading={loading} disabled={code.length !== 6}>
          Verify
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={resend}
            disabled={resending || resendIn > 0}
            className="text-text-muted transition-colors hover:text-text disabled:opacity-50 disabled:hover:text-text-muted tnum"
          >
            {resendIn > 0
              ? `Resend in ${resendIn}s`
              : resending
                ? "Sending…"
                : "Resend code"}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep("form");
              setError(null);
            }}
            className="text-text-muted transition-colors hover:text-text"
          >
            Wrong email? Go back
          </button>
        </div>
      </form>
    );
  }

  if (mode === "waitlist") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex flex-col gap-4"
      >
        <div>
          <h2 className="font-display text-title mb-1">Join the waitlist</h2>
          <p className="text-sm text-text-muted">
            Leave your email and we'll let you know the moment a spot opens
            up.
          </p>
        </div>
        {waitlistStatus ? (
          <p className="text-sm text-success">
            {waitlistStatus === "added"
              ? "You're on the list! We'll email you when a spot opens up."
              : "You're already on the list — we'll be in touch."}
          </p>
        ) : (
          <>
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <Button type="submit" loading={loading}>
              Join waitlist
            </Button>
          </>
        )}
        <button
          type="button"
          disabled={loading}
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          className="text-sm text-text-muted transition-colors hover:text-text text-left disabled:opacity-50"
        >
          ← Back to sign up
        </button>
      </form>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex flex-col gap-4"
    >
      {/* Mode switch — the system segmented control */}
      <div className="inline-flex self-start rounded-pill border border-border bg-surface p-1 text-sm">
        <button
          type="button"
          disabled={loading}
          onClick={() => setMode("login")}
          className={cn(
            "px-4 min-h-[36px] rounded-pill transition-colors disabled:opacity-50",
            mode === "login"
              ? "bg-surface-strong text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
              : "text-text-muted hover:text-text"
          )}
        >
          Sign in
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => setMode("register")}
          className={cn(
            "px-4 min-h-[36px] rounded-pill transition-colors disabled:opacity-50",
            mode === "register"
              ? "bg-surface-strong text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
              : "text-text-muted hover:text-text"
          )}
        >
          Sign up
        </button>
      </div>

      {mode === "register" ? (
        <>
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <Input
            label="Display name (optional)"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="nickname"
          />
          <Input
            label="Invite code"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            autoComplete="off"
          />
          <p className="text-xs text-text-muted">
            No invite code?{" "}
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setMode("waitlist");
                setWaitlistStatus(null);
                setError(null);
              }}
              className="text-amber-hi transition-colors hover:underline disabled:opacity-50"
            >
              Join the waitlist
            </button>
            .
          </p>
        </>
      ) : null}
      <Input
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        required
      />
      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        required
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Button type="submit" loading={loading}>
        {mode === "login" ? "Sign in" : "Create account"}
      </Button>
    </form>
  );
}
