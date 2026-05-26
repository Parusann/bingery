import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EpisodeRow } from "@/features/schedule/EpisodeRow";
import type { ScheduleWeekEpisode } from "@/types/models";

const base: ScheduleWeekEpisode = {
  id: 1,
  anime_id: 99,
  anime: {
    id: 99,
    title: "TestShow",
    title_english: null,
    image_url: "x.jpg",
    popularity: null,
    nsfw_level: null,
  } as any,
  episode_number: 7,
  air_time_utc: "2026-05-24T22:30:00Z",
  type: "sub",
  estimated: false,
  on_watchlist: false,
};

function renderRow(ep: ScheduleWeekEpisode) {
  return render(
    <MemoryRouter>
      <EpisodeRow episode={ep} />
    </MemoryRouter>,
  );
}

describe("EpisodeRow", () => {
  it("renders the episode title, EP number, and badge", () => {
    renderRow(base);
    expect(screen.getByText("TestShow")).toBeInTheDocument();
    expect(screen.getByText("EP 7")).toBeInTheDocument();
    expect(screen.getByText("SUB")).toBeInTheDocument();
  });

  it("renders the EstimatedTag only when estimated=true", () => {
    const { rerender } = renderRow(base);
    expect(screen.queryByText(/estimated/i)).toBeNull();
    rerender(
      <MemoryRouter>
        <EpisodeRow episode={{ ...base, type: "dub", estimated: true }} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/estimated/i)).toBeInTheDocument();
  });

  it("applies highlighted styling when on_watchlist=true", () => {
    renderRow({ ...base, on_watchlist: true });
    const link = screen.getByRole("link");
    expect(link.className).toMatch(/border-gold/);
  });

  it("links to /anime/{anime_id}", () => {
    renderRow(base);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/anime/99");
  });
});
