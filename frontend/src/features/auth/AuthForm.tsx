import { useEffect, useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";

type Mode = "login" | "register";
type Step = "form" | "verify";

const RESEND_SECONDS = 60;

export function AuthForm({ onSuccess }: { onSuccess?: () => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(RESEND_SECONDS);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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
      if (mode === "login") {
        await signIn({ email, password });
        onSuccess?.();
      } else if (step === "form") {
        const normEmail = email.trim().toLowerCase();
        await signUp({
          email: normEmail,
          password,
          username,
          display_name: displayName.trim() || undefined,
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
          <h2 className="font-display text-2xl mb-1">Check your email</h2>
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
          className="text-center tracking-[0.4em] font-mono text-lg"
          required
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {resent && !error ? (
          <p className="text-sm text-text-muted">Code sent.</p>
        ) : null}
        <Button type="submit" loading={loading} disabled={code.length !== 6}>
          Verify
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={resend}
            disabled={resending || resendIn > 0}
            className="text-text-muted hover:text-text disabled:opacity-50 disabled:hover:text-text-muted"
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
            className="text-text-muted hover:text-text"
          >
            Wrong email? Go back
          </button>
        </div>
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
      <div className="flex gap-2 text-sm">
        <button
          type="button"
          onClick={() => setMode("login")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "login"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => setMode("register")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "register"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
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
