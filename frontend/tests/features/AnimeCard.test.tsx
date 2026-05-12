import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AnimeCard } from "@/features/discover/AnimeCard";

const sample = {
  id: 42,
  anilist_id: 1,
  title: "Sample Anime",
  title_english: "Sample Anime EN",
  title_japanese: null,
  description: null,
  image_url: "https://example.com/x.jpg",
  banner_url: null,
  episodes: 12,
  season: null,
  year: 2024,
  format: null,
  status: null,
  api_score: 7.8,
  community_score: null,
  rating_count: null,
  genres: [{ name: "Action" }, { name: "Fantasy" }],
};

describe("AnimeCard", () => {
  it("renders title, score, and genres", () => {
    render(
      <MemoryRouter>
        <AnimeCard anime={sample} />
      </MemoryRouter>
    );
    expect(screen.getByText("Sample Anime EN")).toBeInTheDocument();
    expect(screen.getByText("7.8")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Fantasy")).toBeInTheDocument();
  });

  it("links to detail page", () => {
    render(
      <MemoryRouter>
        <AnimeCard anime={sample} />
      </MemoryRouter>
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "/anime/42");
  });
});
