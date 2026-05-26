import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DayBanner } from "@/features/schedule/DayBanner";
import type { ScheduleWeekEpisode } from "@/types/models";

const ep = (id: number, img: string, on_watchlist = false): ScheduleWeekEpisode => ({
  id,
  anime_id: id,
  anime: { id, title: `T${id}`, title_english: null, image_url: img, popularity: null, nsfw_level: null } as any,
  episode_number: 1,
  air_time_utc: "2026-05-24T22:30:00Z",
  type: "sub",
  estimated: false,
  on_watchlist,
});

describe("DayBanner", () => {
  it("shows weekday name and date", () => {
    render(<DayBanner date="2026-05-24" episodes={[ep(1, "a.jpg")]} isToday={false} />);
    expect(screen.getByText(/Sunday/i)).toBeInTheDocument();
    expect(screen.getByText(/May/i)).toBeInTheDocument();
  });

  it("renders TODAY pill when isToday is true", () => {
    render(<DayBanner date="2026-05-24" episodes={[ep(1, "a.jpg")]} isToday={true} />);
    expect(screen.getByText("TODAY")).toBeInTheDocument();
  });

  it("shows the episode count", () => {
    render(
      <DayBanner
        date="2026-05-24"
        episodes={[ep(1, "a.jpg"), ep(2, "b.jpg"), ep(3, "c.jpg")]}
        isToday={false}
      />,
    );
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText(/episodes?/i)).toBeInTheDocument();
  });

  it("shows watchlist count when any episodes are on watchlist", () => {
    render(
      <DayBanner
        date="2026-05-24"
        episodes={[ep(1, "a.jpg", true), ep(2, "b.jpg", true), ep(3, "c.jpg", false)]}
        isToday={false}
      />,
    );
    expect(screen.getByText(/2 on your watchlist/i)).toBeInTheDocument();
  });

  it("renders an empty-banner variant when episodes is empty", () => {
    render(<DayBanner date="2026-05-24" episodes={[]} isToday={false} />);
    expect(screen.getByText(/No releases/i)).toBeInTheDocument();
  });
});
