import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { AuthForm } from "@/features/auth/AuthForm";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";

describe("AuthForm resend", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    useAuth.setState({ user: null, status: "idle", error: null });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("ignores a second resend click while one is in flight", async () => {
    vi.spyOn(api, "register").mockResolvedValue({
      verification_required: true,
      email: "a@b.c",
    });
    let release!: () => void;
    const resendSpy = vi.spyOn(api, "resendCode").mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ ok: true });
        })
    );

    render(<AuthForm />);
    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "newbie" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@b.c" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    // Flush the signUp promise chain so the verify step renders.
    await act(async () => {});
    screen.getByText("Check your email");

    // Run out the 60s cooldown so the resend button becomes active.
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    const resendBtn = screen.getByRole("button", { name: "Resend code" });
    fireEvent.click(resendBtn);
    fireEvent.click(resendBtn);
    expect(resendSpy).toHaveBeenCalledTimes(1);

    await act(async () => release());
  });
});
