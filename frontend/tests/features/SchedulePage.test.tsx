import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const useScheduleMock = vi.hoisted(() => vi.fn());
const useAnimeEpisodesMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useSchedule", () => ({
  useSchedule: useScheduleMock,
  useAnimeEpisodes: useAnimeEpisodesMock,
}));

import { SchedulePage } from "@/features/schedule/SchedulePage";
import { useAuth } from "@/stores/auth";

const fakeUser = {
  id: 1,
  email: "a@b.c",
  username: "u",
  display_name: null,
  avatar_url: null,
  bio: null,
  created_at: "2026-01-01",
};

beforeEach(() => {
  useScheduleMock.mockReset();
  useAuth.setState({ user: fakeUser, status: "authenticated" });
});

describe("SchedulePage", () => {
  it("shows sign-in prompt when user is not authenticated", () => {
    useAuth.setState({ user: null, status: "idle" });
    useScheduleMock.mockReturnValue({ isLoading: false, data: undefined });
    render(
      <MemoryRouter>
        <SchedulePage />
      </MemoryRouter>
    );
    expect(
      screen.getByText(/Sign in to see the schedule/i)
    ).toBeInTheDocument();
  });

  it("renders skeleton blocks while loading", () => {
    useScheduleMock.mockReturnValue({ isLoading: true, data: undefined });
    const { container } = render(
      <MemoryRouter>
        <SchedulePage />
      </MemoryRouter>
    );
    expect(container.querySelectorAll(".h-24")).toHaveLength(5);
    expect(
      screen.queryByText(/No releases scheduled/i)
    ).not.toBeInTheDocument();
  });

  it("renders skeleton blocks when query has no data yet", () => {
    useScheduleMock.mockReturnValue({ isLoading: false, data: undefined });
    const { container } = render(
      <MemoryRouter>
        <SchedulePage />
      </MemoryRouter>
    );
    expect(container.querySelectorAll(".h-24")).toHaveLength(5);
  });

  it("renders empty-state message when day has no episodes", () => {
    useScheduleMock.mockReturnValue({
      isLoading: false,
      data: { days: [{ date: "2026-05-14", episodes: [] }] },
    });
    render(
      <MemoryRouter>
        <SchedulePage />
      </MemoryRouter>
    );
    expect(screen.getByText("No releases scheduled.")).toBeInTheDocument();
  });
});
