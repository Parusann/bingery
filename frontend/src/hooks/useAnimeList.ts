import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Params {
  page?: number;
  perPage?: number;
  search?: string;
  genre?: string;
  sort?: string;
  order?: "asc" | "desc";
}

export function useAnimeList(params: Params = {}) {
  const {
    page = 1,
    perPage = 24,
    search = "",
    genre = "",
    sort = "api_score",
    order = "desc",
  } = params;
  const qs = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    sort,
    order,
  });
  if (search) qs.set("search", search);
  if (genre) qs.set("genre", genre);
  const key = ["anime-list", page, perPage, search, genre, sort, order];
  return useQuery({
    queryKey: key,
    queryFn: () => api.getAnime("?" + qs.toString()),
  });
}
