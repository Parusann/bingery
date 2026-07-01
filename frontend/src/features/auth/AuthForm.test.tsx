// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthForm } from "./AuthForm";

const { joinWaitlist, register } = vi.hoisted(() => ({
  joinWaitlist: vi.fn(),
  register: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    joinWaitlist,
    register,
    getToken: () => null,
    setToken: () => {},
  },
  ApiError: class ApiError extends Error {},
  onUnauthorized: () => {},
}));

async function openWaitlistAndSubmit(email: string) {
  render(<AuthForm />);
  await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Join the waitlist" })
  );
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.click(screen.getByRole("button", { name: "Join waitlist" }));
}

describe("AuthForm waitlist", () => {
  beforeEach(() => {
    joinWaitlist.mockReset();
  });

  it("submits the normalized email and confirms the signup", async () => {
    joinWaitlist.mockResolvedValue({ status: "added" });
    await openWaitlistAndSubmit("Fan@Example.com");
    expect(joinWaitlist).toHaveBeenCalledWith({ email: "fan@example.com" });
    expect(await screen.findByText(/you're on the list/i)).toBeTruthy();
  });

  it("tells a repeat signup it is already on the list", async () => {
    joinWaitlist.mockResolvedValue({ status: "already" });
    await openWaitlistAndSubmit("dupe@example.com");
    expect(await screen.findByText(/already on the list/i)).toBeTruthy();
  });

  it("surfaces API errors without leaving the form", async () => {
    joinWaitlist.mockRejectedValue(
      new Error("Please enter a valid email address.")
    );
    await openWaitlistAndSubmit("fan@example.com");
    expect(
      await screen.findByText("Please enter a valid email address.")
    ).toBeTruthy();
    // The form is still there for a retry.
    expect(screen.getByRole("button", { name: "Join waitlist" })).toBeTruthy();
  });

  it("locks the back button while the waitlist request is in flight", async () => {
    let resolveJoin!: (v: { status: "added" }) => void;
    joinWaitlist.mockImplementation(
      () => new Promise((r) => (resolveJoin = r))
    );
    await openWaitlistAndSubmit("fan@example.com");
    const back = screen.getByRole("button", { name: /back to sign up/i });
    expect(back).toHaveProperty("disabled", true);
    resolveJoin({ status: "added" });
    expect(await screen.findByText(/you're on the list/i)).toBeTruthy();
  });

  it("locks 'Join the waitlist' while a sign-up request is in flight", async () => {
    register.mockImplementation(() => new Promise(() => {}));
    render(<AuthForm />);
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    await userEvent.type(screen.getByLabelText("Username"), "fan");
    await userEvent.type(screen.getByLabelText("Email"), "fan@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22");
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" })
    );
    expect(
      screen.getByRole("button", { name: "Join the waitlist" })
    ).toHaveProperty("disabled", true);
  });

  it("locks the mode tabs while a request is in flight", async () => {
    register.mockImplementation(() => new Promise(() => {}));
    render(<AuthForm />);
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    await userEvent.type(screen.getByLabelText("Username"), "fan");
    await userEvent.type(screen.getByLabelText("Email"), "fan@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter22");
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" })
    );
    expect(screen.getByRole("button", { name: "Sign in" })).toHaveProperty(
      "disabled",
      true
    );
    expect(screen.getByRole("button", { name: "Sign up" })).toHaveProperty(
      "disabled",
      true
    );
  });

  it("returns to the sign-up form from the waitlist view", async () => {
    render(<AuthForm />);
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Join the waitlist" })
    );
    await userEvent.click(
      screen.getByRole("button", { name: /back to sign up/i })
    );
    expect(screen.getByLabelText("Invite code")).toBeTruthy();
  });
});
