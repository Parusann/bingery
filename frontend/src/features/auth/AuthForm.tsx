import { useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";

type Mode = "login" | "register";

export function AuthForm({ onSuccess }: { onSuccess?: () => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const signIn = useAuth((s) => s.signIn);
  const signUp = useAuth((s) => s.signUp);

  const submit = async () => {
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") await signIn({ email, password });
      else await signUp({ email, password, username });
      onSuccess?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

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
          Create account
        </button>
      </div>

      {mode === "register" ? (
        <Input
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
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
