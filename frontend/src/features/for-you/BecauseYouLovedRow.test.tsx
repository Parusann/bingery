// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BecauseYouLovedRow } from "./BecauseYouLovedRow";
import type { SimilarAnime } from "@/types/api";
import type { AnimeSummary } from "@/types/models";

function anime(id: number, title: string): AnimeSummary {
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
  } as AnimeSummary;
}

describe("BecauseYouLovedRow", () => {
  it("renders the seed title and item cards", () => {
    const data = {
      seed: anime(1, "Loved Seed"),
      items: [
        { ...anime(2, "Suggested Sib"), match_score: 82, shared_tags: ["Isekai"], in_plan_to_watch: false } as SimilarAnime,
      ],
    };
    render(
      <MemoryRouter>
        <BecauseYouLovedRow data={data} />
      </MemoryRouter>
    );
    expect(screen.getByText(/because you loved/i)).toBeTruthy();
    expect(screen.getByText("Loved Seed")).toBeTruthy();
    expect(screen.getByText("Suggested Sib")).toBeTruthy();
  });

  it("renders nothing without data", () => {
    const { container } = render(
      <MemoryRouter>
        <BecauseYouLovedRow data={undefined} />
      </MemoryRouter>
    );
    expect(container.innerHTML).toBe("");
  });
});
