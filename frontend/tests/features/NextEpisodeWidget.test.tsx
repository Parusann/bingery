import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const useScheduleMock = vi.hoisted(() => vi.fn());
const useAnimeEpisodesMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useSchedule", () => ({
  useSchedule: useScheduleMock,
  useAnimeEpisodes: useAnimeEpisodesMock,
}));

import { NextEpisodeWidget } from "@/features/details/NextEpisodeWidget";

const baseEpisode = {
  id: 1,
  anime_id: 42,
  episode_number: 7,
  title: null,
  air_date_sub: null,
  air_date_dub: null,
  dub_source: null,
};

beforeEach(() => {
  useAnimeEpisodesMock.mockReset();
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-05-14T00:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("NextEpisodeWidget", () => {
  it("renders nothing when query has no data", () => {
    useAnimeEpisodesMock.mockReturnValue({ data: undefined });
    const { container } = render(<NextEpisodeWidget animeId={42} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when next_sub and next_dub are both absent", () => {
    useAnimeEpisodesMock.mockReturnValue({
      data: { next_sub: null, next_dub: null },
    });
    const { container } = render(<NextEpisodeWidget animeId={42} />);
    expect(container.firstChild).toBeNull();
  });

  it("formats sub airtime within 24h as Xh Ym", () => {
    useAnimeEpisodesMock.mockReturnValue({
      data: {
        next_sub: {
          ...baseEpisode,
          episode_number: 12,
          air_date_sub: "2026-05-14T05:30:00Z",
        },
        next_dub: null,
      },
    });
    render(<NextEpisodeWidget animeId={42} />);
    expect(
      screen.getByText(/Episode 12 \(sub\) airs in 5h 30m/)
    ).toBeInTheDocument();
  });

  it("formats dub airtime over 24h as Xd Yh", () => {
    useAnimeEpisodesMock.mockReturnValue({
      data: {
        next_sub: null,
        next_dub: {
          ...baseEpisode,
          episode_number: 5,
          air_date_dub: "2026-05-16T03:00:00Z",
        },
      },
    });
    render(<NextEpisodeWidget animeId={42} />);
    expect(
      screen.getByText(/Episode 5 \(dub\) airs in 2d 3h/)
    ).toBeInTheDocument();
  });

  it("renders both sub and dub pills when both are present", () => {
    useAnimeEpisodesMock.mockReturnValue({
      data: {
        next_sub: {
          ...baseEpisode,
          episode_number: 8,
          air_date_sub: "2026-05-14T12:00:00Z",
        },
        next_dub: {
          ...baseEpisode,
          id: 2,
          episode_number: 3,
          air_date_dub: "2026-05-15T00:00:00Z",
        },
      },
    });
    render(<NextEpisodeWidget animeId={42} />);
    expect(
      screen.getByText(/Episode 8 \(sub\) airs in 12h 0m/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Episode 3 \(dub\) airs in 1d 0h/)
    ).toBeInTheDocument();
  });

  it("shows 'now' when air time has already passed", () => {
    useAnimeEpisodesMock.mockReturnValue({
      data: {
        next_sub: {
          ...baseEpisode,
          episode_number: 1,
          air_date_sub: "2026-05-13T00:00:00Z",
        },
        next_dub: null,
      },
    });
    render(<NextEpisodeWidget animeId={42} />);
    expect(
      screen.getByText(/Episode 1 \(sub\) airs in now/)
    ).toBeInTheDocument();
  });
});
