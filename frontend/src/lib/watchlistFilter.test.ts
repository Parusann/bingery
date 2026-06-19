import { describe, it, expect } from "vitest";
import {
  filterAndSortEntries,
  deriveGenreOptions,
  deriveStatusCounts,
} from "./watchlistFilter";
import type { WatchEntry, WatchStatus } from "@/types/models";

function entry(o: {
  id: number;
  title?: string;
  titleEn?: string | null;
  status?: WatchStatus;
  favorite?: boolean;
  score?: number | null;
  created?: string;
  updated?: string;
  official?: string[];
  fan?: string[];
}): WatchEntry {
  return {
    id: o.id,
    status: o.status ?? "watching",
    episodes_watched: 0,
    is_favorite: o.favorite ?? false,
    created_at: o.created ?? "2024-01-01T00:00:00",
    updated_at: o.updated ?? "2024-01-01T00:00:00",
    score: o.score ?? null,
    genres: o.fan ?? [],
    anime: {
      id: o.id,
      anilist_id: null,
      title: o.title ?? `Show ${o.id}`,
      title_english: o.titleEn ?? null,
      title_japanese: null,
      description: null,
      image_url: null,
      banner_url: null,
      episodes: null,
      season: null,
      year: null,
      format: null,
      status: null,
      api_score: null,
      community_score: null,
      rating_count: null,
      official_genres: (o.official ?? []).map((name) => ({ name })),
    },
  };
}

const base = {
  status: null as WatchStatus | null,
  q: "",
  genres: [] as string[],
  genreMode: "any" as const,
  favoritesOnly: false,
  sort: "updated" as const,
};

describe("filterAndSortEntries", () => {
  it("searches title and English title, case-insensitively", () => {
    const list = [
      entry({ id: 1, title: "Dragon Ball" }),
      entry({ id: 2, title: "Naruto", titleEn: "Ninja Tale" }),
      entry({ id: 3, title: "Bleach" }),
    ];
    expect(filterAndSortEntries(list, { ...base, q: "dragon" }).map((e) => e.id)).toEqual([1]);
    expect(filterAndSortEntries(list, { ...base, q: "ninja" }).map((e) => e.id)).toEqual([2]);
  });

  it("matches ANY selected genre across official + fan genres", () => {
    const list = [
      entry({ id: 1, official: ["Action"] }),
      entry({ id: 2, fan: ["Comedy"] }),
      entry({ id: 3, official: ["Drama"] }),
    ];
    const out = filterAndSortEntries(list, { ...base, genres: ["Action", "Comedy"], genreMode: "any" });
    expect(out.map((e) => e.id).sort()).toEqual([1, 2]);
  });

  it("matches ALL selected genres when genreMode is all", () => {
    const list = [
      entry({ id: 1, official: ["Action"], fan: ["Comedy"] }),
      entry({ id: 2, official: ["Action"] }),
    ];
    const out = filterAndSortEntries(list, { ...base, genres: ["Action", "Comedy"], genreMode: "all" });
    expect(out.map((e) => e.id)).toEqual([1]);
  });

  it("filters favorites only", () => {
    const list = [entry({ id: 1, favorite: true }), entry({ id: 2, favorite: false })];
    expect(filterAndSortEntries(list, { ...base, favoritesOnly: true }).map((e) => e.id)).toEqual([1]);
  });

  it("sorts by title A-Z using the display title", () => {
    const list = [entry({ id: 1, title: "Zeta" }), entry({ id: 2, title: "Alpha" })];
    expect(filterAndSortEntries(list, { ...base, sort: "title" }).map((e) => e.id)).toEqual([2, 1]);
  });

  it("sorts by your score descending, nulls last", () => {
    const list = [
      entry({ id: 1, score: 5 }),
      entry({ id: 2, score: null }),
      entry({ id: 3, score: 9 }),
    ];
    expect(filterAndSortEntries(list, { ...base, sort: "score" }).map((e) => e.id)).toEqual([3, 1, 2]);
  });

  it("sorts by date added descending", () => {
    const list = [
      entry({ id: 1, created: "2024-01-01T00:00:00" }),
      entry({ id: 2, created: "2024-05-01T00:00:00" }),
    ];
    expect(filterAndSortEntries(list, { ...base, sort: "created" }).map((e) => e.id)).toEqual([2, 1]);
  });

  it("filters by status", () => {
    const list = [
      entry({ id: 1, status: "completed" }),
      entry({ id: 2, status: "watching" }),
    ];
    expect(filterAndSortEntries(list, { ...base, status: "completed" }).map((e) => e.id)).toEqual([1]);
  });
});

describe("deriveGenreOptions", () => {
  it("returns the sorted unique union of official and fan genres", () => {
    const list = [
      entry({ id: 1, official: ["Action", "Drama"], fan: ["Comedy"] }),
      entry({ id: 2, official: ["Action"], fan: ["Isekai"] }),
    ];
    expect(deriveGenreOptions(list)).toEqual(["Action", "Comedy", "Drama", "Isekai"]);
  });
});

describe("deriveStatusCounts", () => {
  it("counts per status and favorites", () => {
    const list = [
      entry({ id: 1, status: "watching", favorite: true }),
      entry({ id: 2, status: "watching" }),
      entry({ id: 3, status: "completed", favorite: true }),
    ];
    const c = deriveStatusCounts(list);
    expect(c.watching).toBe(2);
    expect(c.completed).toBe(1);
    expect(c.favorites).toBe(2);
  });
});
