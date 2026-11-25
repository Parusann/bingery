import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { AuthPage, pathAfterAuth } from "./AuthPage";
import { useAuth } from "@/stores/auth";

function Destination() {
  const { pathname, search, hash } = useLocation();
  return <p>{pathname + search + hash}</p>;
}

describe("account entry points", () => {
  it("returns a signed-in visitor to their saved route with its filters", async () => {
    const signIn = vi.fn().mockResolvedValue(undefined);
    const original = useAuth.getState().signIn;
    useAuth.setState({ signIn });
    try {
      render(
        <MemoryRouter initialEntries={[{ pathname: "/auth", state: { returnTo: "/watchlist?status=watching#recent" } }]}>
          <Routes>
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/watchlist" element={<Destination />} />
          </Routes>
        </MemoryRouter>
      );
      await userEvent.type(screen.getByLabelText("Email"), "Fan@Example.com");
      await userEvent.type(screen.getByLabelText("Password"), "sample-password{Enter}");
      expect(signIn).toHaveBeenCalledWith({ email: "fan@example.com", password: "sample-password" });
      expect(await screen.findByText("/watchlist?status=watching#recent")).toBeTruthy();
    } finally {
      useAuth.setState({ signIn: original });
    }
  });

  it.each([undefined, "/auth/?invite=old", "https://example.com", "//example.com", "/a/..//example.com", "/\\example.com"])(
    "defaults to the catalog for an unusable return path %s", (value) => {
      expect(pathAfterAuth(value)).toBe("/discover");
    }
  );

  it("prefills a personal invitation and prioritizes it over the waitlist", () => {
    render(<MemoryRouter initialEntries={["/auth?mode=waitlist&invite=example-code&email=fan%40example.com"]}><AuthPage /></MemoryRouter>);
    expect(screen.getByLabelText("Email")).toHaveValue("fan@example.com");
    expect(screen.getByLabelText("Invite code")).toHaveValue("example-code");
    expect(screen.getByRole("heading", { name: "Create an account" })).toBeVisible();
  });
});
