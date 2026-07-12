// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WaitlistAdmin } from "./WaitlistAdmin";
import { useAuth } from "@/stores/auth";
import type { User, WaitlistEntry } from "@/types/models";

const { waitlistAdmin, waitlistAdminApprove } = vi.hoisted(() => ({
  waitlistAdmin: vi.fn(),
  waitlistAdminApprove: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    waitlistAdmin,
    waitlistAdminApprove,
    getToken: () => null,
    setToken: () => {},
  },
  ApiError: class ApiError extends Error {},
  onUnauthorized: () => {},
}));

const owner: User = {
  id: 1,
  email: "owner@example.com",
  username: "owner",
  display_name: null,
  avatar_url: null,
  bio: null,
  created_at: "2026-01-01T00:00:00Z",
  is_owner: true,
};

function mkEntry(overrides: Partial<WaitlistEntry> = {}): WaitlistEntry {
  return {
    id: 1,
    email: "fan@example.com",
    created_at: "2026-07-01T12:00:00Z",
    status: "pending",
    invite_code: null,
    approved_at: null,
    code_used_at: null,
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={qc}>
      <WaitlistAdmin />
    </QueryClientProvider>
  );
}

describe("WaitlistAdmin", () => {
  beforeEach(() => {
    waitlistAdmin.mockReset();
    waitlistAdminApprove.mockReset();
    useAuth.setState({ user: owner, status: "authenticated" });
  });

  it("shows 'Not authorized' and does not fetch when signed out", () => {
    useAuth.setState({ user: null, status: "idle" });
    renderPage();
    expect(screen.getByText("Not authorized")).toBeTruthy();
    expect(waitlistAdmin).not.toHaveBeenCalled();
  });

  it("shows 'Not authorized' for a signed-in non-owner", () => {
    useAuth.setState({ user: { ...owner, is_owner: false } });
    renderPage();
    expect(screen.getByText("Not authorized")).toBeTruthy();
    expect(waitlistAdmin).not.toHaveBeenCalled();
  });

  it("renders entries with status and invite code for the owner", async () => {
    waitlistAdmin.mockResolvedValue({
      entries: [
        mkEntry({ id: 1, email: "pending@example.com" }),
        mkEntry({
          id: 2,
          email: "approved@example.com",
          status: "approved",
          invite_code: "BINGE-XYZ",
          approved_at: "2026-07-02T12:00:00Z",
        }),
      ],
    });
    renderPage();
    expect(await screen.findByText("pending@example.com")).toBeTruthy();
    expect(screen.getByText("approved@example.com")).toBeTruthy();
    expect(screen.getByText("pending")).toBeTruthy();
    expect(screen.getByText("approved")).toBeTruthy();
    expect(screen.getByText("BINGE-XYZ")).toBeTruthy();
    // Only the pending entry gets an Approve button.
    expect(screen.getAllByRole("button", { name: "Approve" })).toHaveLength(1);
  });

  it("approves a pending entry and refreshes the list", async () => {
    const approved = mkEntry({
      status: "approved",
      invite_code: "BINGE-NEW",
      approved_at: "2026-07-03T12:00:00Z",
    });
    waitlistAdmin
      .mockResolvedValueOnce({ entries: [mkEntry()] })
      .mockResolvedValueOnce({ entries: [approved] });
    waitlistAdminApprove.mockResolvedValue({ entry: approved });

    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Approve" })
    );
    expect(waitlistAdminApprove).toHaveBeenCalledWith(1);
    // The invalidated query refetches and shows the minted code.
    expect(await screen.findByText("BINGE-NEW")).toBeTruthy();
  });

  it("surfaces approve errors without dropping the entry", async () => {
    waitlistAdmin.mockResolvedValue({ entries: [mkEntry()] });
    waitlistAdminApprove.mockRejectedValue(
      new Error("Invite email failed to send. Try again.")
    );
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: "Approve" })
    );
    expect(
      await screen.findByText("Invite email failed to send. Try again.")
    ).toBeTruthy();
    // The row is still there for a retry.
    expect(screen.getByText("fan@example.com")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
  });
});
