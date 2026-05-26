import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const useScheduleWeekMock = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/useScheduleWeek", () => ({
  useScheduleWeek: useScheduleWeekMock,
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

const sevenEmptyDays = (weekStart: string) => {
  const out = [];
  const [y, m, d] = weekStart.split("-").map(Number);
  for (let i = 0; i < 7; i++) {
    const dt = new Date(Date.UTC(y, m - 1, d + i));
    out.push({ date: dt.toISOString().slice(0, 10), episodes: [] });
  }
  return out;
};

beforeEach(() => {
  useScheduleWeekMock.mockReset();
  useAuth.setState({ user: fakeUser, status: "authenticated" });
});

describe("SchedulePage", () => {
  it("renders the sign-in prompt when unauthenticated", () => {
    useAuth.setState({ user: null, status: "idle" });
    useScheduleWeekMock.mockReturnValue({ isLoading: false, data: undefined });
    render(
      <MemoryRouter initialEntries={["/schedule"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/sign in to see the schedule/i)).toBeInTheDocument();
  });

  it("renders the header, day strip, and 7 sections when data loads", () => {
    useScheduleWeekMock.mockReturnValue({
      isLoading: false,
      data: { week_start: "2026-05-24", days: sevenEmptyDays("2026-05-24") },
    });
    const { container } = render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/what's/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/previous week/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/next week/i)).toBeInTheDocument();
    expect(container.querySelectorAll('section[id^="day-"]').length).toBe(7);
  });

  it("renders skeletons while loading", () => {
    useScheduleWeekMock.mockReturnValue({ isLoading: true, data: undefined });
    const { container } = render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(container.querySelectorAll('[data-skeleton="true"]').length).toBeGreaterThan(0);
  });

  it("passes lang and mine from URL into useScheduleWeek", () => {
    useScheduleWeekMock.mockReturnValue({
      isLoading: false,
      data: { week_start: "2026-05-24", days: sevenEmptyDays("2026-05-24") },
    });
    render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24&lang=dub&mine=1"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(useScheduleWeekMock).toHaveBeenCalledWith("2026-05-24", "dub", true);
  });
});
