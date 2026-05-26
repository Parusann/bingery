import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DaySection } from "@/features/schedule/DaySection";
import type { ScheduleWeekEpisode } from "@/types/models";

const ep = (id: number, on_watchlist: boolean): ScheduleWeekEpisode => ({
  id,
  anime_id: id,
  anime: { id, title: `T${id}`, title_english: null, image_url: "x.jpg", popularity: null, nsfw_level: null } as any,
  episode_number: id,
  air_time_utc: "2026-05-24T20:00:00Z",
  type: "sub",
  estimated: false,
  on_watchlist,
});

describe("DaySection", () => {
  it("renders the banner and both episode groups", () => {
    render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[ep(1, true), ep(2, false), ep(3, true)]}
          isToday={false}
          myShowsOnly={false}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("T2")).toBeInTheDocument();
    expect(screen.getByText("T3")).toBeInTheDocument();
  });

  it("only renders watchlist episodes when myShowsOnly is true", () => {
    render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[ep(1, true), ep(2, false)]}
          isToday={false}
          myShowsOnly={true}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.queryByText("T2")).toBeNull();
  });

  it("has a section id of day-<date> for smooth-scrolling", () => {
    const { container } = render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[]}
          isToday={false}
          myShowsOnly={false}
        />
      </MemoryRouter>,
    );
    expect(container.querySelector("#day-2026-05-24")).not.toBeNull();
  });
});
