import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { DiscoverPage } from "@/features/discover/DiscoverPage";
import { api } from "@/lib/api";
import type { AnimeSummary } from "@/types/models";

const title: AnimeSummary = {
  id: 7, anilist_id: null, title: "Example", title_english: null, title_japanese: null,
  image_url: null, banner_url: null, episodes: 12, season: null, year: 2024, status: "Finished",
  api_score: 8.2, community_score: null, rating_count: 0,
};

function showPage(url = "/discover") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  function Location() {
    const location = useLocation();
    return <output aria-label="Current location">{location.pathname}{location.search}</output>;
  }
  render(
    <QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/discover" element={<DiscoverPage />} />
        <Route path="/anime/:id" element={<h1>Title detail</h1>} />
      </Routes>
      <Location />
    </MemoryRouter></QueryClientProvider>
  );
  return screen.getByLabelText("Current location");
}

describe("Discover", () => {
  beforeEach(() => {
    vi.spyOn(api, "getCatalogGenres").mockResolvedValue({ all: [{ name: "Action" }] });
    vi.spyOn(api, "autocomplete").mockResolvedValue({ results: [title] });
    vi.spyOn(api, "getAnime").mockImplementation(async (query) => ({
      anime: [title], total: 48, pages: 2, page: Number(new URLSearchParams(query).get("page")),
    }));
  });
  afterEach(() => vi.restoreAllMocks());

  it("restores the search and page from the URL and resets pagination when sorting", async () => {
    const user = userEvent.setup();
    const location = showPage("/discover?q=Example&page=2");
    expect(screen.getByRole("combobox", { name: "Search anime" })).toHaveValue("Example");
    expect(await screen.findByText("Page 2 of 2")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Sort by" }), "title");
    expect(await screen.findByText("Page 1 of 2")).toBeInTheDocument();
    expect(location).toHaveTextContent("/discover?q=Example&sort=title");
    expect(api.getAnime).toHaveBeenLastCalledWith(expect.stringContaining("sort=title&order=asc"));
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(location).toHaveTextContent("/discover?sort=title");
  });

  it("selects a suggestion with the keyboard and still supports searching all matches", async () => {
    const user = userEvent.setup();
    const location = showPage();
    const search = screen.getByRole("combobox", { name: "Search anime" });
    await user.type(search, "exam");
    await screen.findByRole("option", { name: /Example/ });
    await user.keyboard("{Escape}{Enter}");
    expect(location).toHaveTextContent("/discover?q=exam");
    await user.type(search, "p");
    await screen.findByRole("option", { name: /Example/ });
    await user.keyboard("{ArrowDown}{Enter}");
    expect(location).toHaveTextContent("/anime/7");
  });

  it("recovers from a request error and keeps an empty search distinct", async () => {
    vi.mocked(api.getAnime).mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce({
      anime: [], total: 0, pages: 0, page: 1,
    });
    const location = showPage("/discover?genre=Action");
    const user = userEvent.setup();
    expect(await screen.findByRole("alert")).toHaveTextContent("catalog couldn’t load");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No matching titles.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(location.textContent).toBe("/discover");
    expect(await screen.findByRole("heading", { name: "Example" })).toBeInTheDocument();
  });
});
