// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SimilarStrip } from "./SimilarStrip";
import type { SimilarAnime } from "@/types/api";

function mk(id: number, title: string, shared_tags: string[]): SimilarAnime {
  return {
    id,
    anilist_id: null,
    title,
    title_english: null,
    title_japanese: null,
    description: null,
    image_url: null,
    banner_url: null,
    episodes: 25,
    season: null,
    year: 2016,
    format: null,
    status: null,
    api_score: 8,
    community_score: null,
    rating_count: null,
    genres: [],
    match_score: 80,
    shared_tags,
    in_plan_to_watch: false,
  } as SimilarAnime;
}

describe("SimilarStrip", () => {
  it("renders cards with shared-tag badges", () => {
    render(
      <MemoryRouter>
        <SimilarStrip similar={[mk(1, "Twin Show", ["Isekai", "Time Loop"])]} />
      </MemoryRouter>
    );
    expect(screen.getByText("Twin Show")).toBeTruthy();
    expect(screen.getByText("Isekai")).toBeTruthy();
    expect(screen.getByText("Time Loop")).toBeTruthy();
  });

  it("renders nothing when empty", () => {
    const { container } = render(
      <MemoryRouter>
        <SimilarStrip similar={[]} />
      </MemoryRouter>
    );
    expect(container.innerHTML).toBe("");
  });
});
