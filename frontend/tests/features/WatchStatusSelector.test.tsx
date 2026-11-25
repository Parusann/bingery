import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WatchStatusSelector } from "@/features/watchlist/WatchStatusSelector";
import { useAnimeDetail } from "@/hooks/useAnimeDetail";
import { api } from "@/lib/api";
import type { AnimeDetail, WatchEntry } from "@/types/models";

const anime: AnimeDetail = {
  id: 7, anilist_id: null, title: "Example", title_english: null, title_japanese: null,
  image_url: null, banner_url: null, episodes: 12, season: null, year: null, status: null,
  api_score: null, community_score: null, rating_count: 0,
};
const entry: WatchEntry = {
  id: 3, anime, status: "on_hold", episodes_watched: 2, is_favorite: true,
  updated_at: "", created_at: "",
};

function showProgress(total: number | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["anime-detail", anime.id, undefined], { anime: { ...anime, user_watch_status: entry } });
  function Detail() {
    const status = useAnimeDetail(anime.id).data?.anime.user_watch_status;
    return <WatchStatusSelector animeId={anime.id} current={status?.status ?? null}
      isFavorite={!!status?.is_favorite} watched={status?.episodes_watched ?? 0} total={total} />;
  }
  render(<QueryClientProvider client={client}><Detail /></QueryClientProvider>);
  return {
    count: screen.getByRole("spinbutton", { name: "Episodes watched" }),
    save: screen.getByRole("button", { name: "Save progress" }),
  };
}

afterEach(() => vi.restoreAllMocks());

describe("episode progress", () => {
  it("rejects invalid counts and keeps the draft available after a failed save", async () => {
    const update = vi.spyOn(api, "setWatchStatus")
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockResolvedValue({ entry: { ...entry, episodes_watched: 0 } });
    vi.spyOn(api, "getAnimeDetail").mockRejectedValue(new Error("Refresh unavailable"));
    const { count, save } = showProgress(12);
    for (const invalid of ["", "-1", "2.5", "13"]) {
      fireEvent.change(count, { target: { value: invalid } });
      expect(save).toBeDisabled();
    }
    fireEvent.change(count, { target: { value: "0" } });
    fireEvent.click(save);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
    expect(count).toHaveValue(0);
    fireEvent.click(save);
    expect(await screen.findByRole("status")).toHaveTextContent("Progress saved");
    expect(update).toHaveBeenLastCalledWith(7, { status: "on_hold", episodes_watched: 0 });
    expect(count).toHaveValue(0);
    expect(save).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove from favorites" })).toHaveAttribute("aria-pressed", "true");
  });

  it("accepts progress for a series with an unknown total and submits only once", async () => {
    let finish!: (value: { entry: WatchEntry }) => void;
    const update = vi.spyOn(api, "setWatchStatus").mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    vi.spyOn(api, "getAnimeDetail").mockResolvedValue({ anime: { ...anime, user_watch_status: { ...entry, episodes_watched: 42 } } });
    const { count, save } = showProgress(null);
    fireEvent.change(count, { target: { value: "42" } });
    fireEvent.click(save);
    fireEvent.click(save);
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    finish({ entry: { ...entry, episodes_watched: 42 } });
    expect(await screen.findByRole("status")).toHaveTextContent("Progress saved");
    expect(count).toHaveValue(42);
  });
});
