import { useEffect, useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

type Mode = "login" | "register" | "waitlist";
type Step = "form" | "verify" | "resume";

const RESEND_SECONDS = 60;

interface AuthFormProps {
  onSuccess?: () => void;
  /** Prefill from an invite email link (/auth?invite=<code>&email=<address>). */
  initialEmail?: string;
  initialInviteCode?: string;
  initialMode?: Mode;
}

export function AuthForm({
  onSuccess,
  initialEmail,
  initialInviteCode,
  initialMode = "login",
}: AuthFormProps) {
  // An invite link lands straight on the sign-up form with code + email set.
  const [mode, setMode] = useState<Mode>(
    initialInviteCode ? "register" : initialMode
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
    if (step === "form" || resendIn <= 0) return;
    const t = setInterval(() => setResendIn((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [step, resendIn]);

  const submit = async () => {
    if (loading || resending) return;
    setError(null);
    setLoading(true);
    try {
      if (mode === "waitlist") {
        const res = await api.joinWaitlist({
          email: email.trim().toLowerCase(),
        });
        setWaitlistStatus(res.status);
      } else if (mode === "login") {
        await signIn({ email: email.trim().toLowerCase(), password });
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
    if (loading || resending || resendIn > 0) return;
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

  if (step !== "form") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="auth-form flex flex-col gap-4"
        aria-busy={loading || resending}
      >
        <div>
          <h1>{step === "resume" ? "Finish signing up" : "Check your email"}</h1>
          <p className="text-sm text-text-muted">
            {step === "resume" ? "Enter the email and six-digit code from your signup." : <>We sent a 6-digit code to <span className="text-text">{email}</span>.</>}
          </p>
        </div>
        {step === "resume" && (
          <Input
            label="Email" name="email" type="email" autoComplete="email" maxLength={120}
            value={email} onChange={(e) => { setEmail(e.target.value); setResent(false); }}
            disabled={loading || resending} required autoFocus
          />
        )}
        <Input
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          name="code"
          autoFocus={step === "verify"}
          className="text-center tracking-[0.4em] font-mono tnum text-lg"
          required
        />
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {resent && !error ? (
          <p role="status" className="text-sm text-success">Code sent.</p>
        ) : null}
        <Button type="submit" loading={loading} disabled={resending || code.length !== 6}>
          Verify
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={(event) => {
              const input = event.currentTarget.form?.elements.namedItem("email");
              if (input instanceof HTMLInputElement && !input.reportValidity()) return;
              void resend();
            }}
            disabled={loading || resending || resendIn > 0}
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
            disabled={loading || resending}
            onClick={() => {
              setStep("form");
              setError(null);
            }}
            className="text-text-muted transition-colors hover:text-text"
          >
            {step === "resume" ? "Back to sign up" : "Wrong email? Go back"}
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
        className="auth-form flex flex-col gap-4"
        aria-busy={loading}
      >
        <div>
          <h1>Join the waitlist</h1>
          <p className="text-sm text-text-muted">
            Leave your email and we'll let you know the moment a spot opens
            up.
          </p>
        </div>
        {waitlistStatus ? (
          <p role="status" className="text-sm text-success">
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
              name="email"
              maxLength={120}
              required
            />
            {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
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
      className="auth-form flex flex-col gap-4"
      aria-busy={loading}
    >
      <div>
        <h1>{mode === "login" ? "Welcome back" : "Create an account"}</h1>
        <p className="text-sm text-text-muted">
          {mode === "login" ? "Sign in to your watchlist, ratings, and recommendations." : "Use the invite code sent to your email to join Bingery."}
        </p>
      </div>
      <div className="auth-mode" role="group" aria-label="Account access">
        <button
          type="button"
          disabled={loading}
          aria-pressed={mode === "login"}
          onClick={() => { setMode("login"); setError(null); }}
        >
          Sign in
        </button>
        <button
          type="button"
          disabled={loading}
          aria-pressed={mode === "register"}
          onClick={() => { setMode("register"); setError(null); }}
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
            name="username"
            minLength={3}
            maxLength={80}
            required
          />
          <Input
            label="Display name (optional)"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="nickname"
            name="display_name"
          />
          <Input
            label="Invite code"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            autoComplete="off"
            name="invite_code"
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
        name="email"
        maxLength={120}
        required
      />
      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        name="password"
        minLength={mode === "register" ? 6 : undefined}
        required
      />
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      <Button type="submit" loading={loading}>
        {mode === "login" ? "Sign in" : "Create account"}
      </Button>
      {mode === "register" && (
        <button
          type="button"
          className="self-center text-sm text-amber-hi hover:underline"
          disabled={loading}
          onClick={() => {
            setError(null);
            setResent(false);
            setCode("");
            setResendIn(0);
            setStep("resume");
          }}
        >
          Already have a verification code?
        </button>
      )}
    </form>
  );
}
