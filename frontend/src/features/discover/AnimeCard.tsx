import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Star } from "lucide-react";
import type { AnimeSummary } from "@/types/models";
import { cn } from "@/lib/cn";
import "./catalog.css";

interface Props {
  anime: AnimeSummary;
  index?: number;
  compact?: boolean;
  featured?: boolean;
  scoreSource?: "api_score" | "community_score";
}

export function AnimeCard({ anime, compact, featured, scoreSource }: Props) {
  const [failedImages, setFailedImages] = useState<string[]>([]);
  const title = anime.title_english || anime.title;
  const artwork = [featured && anime.banner_url, anime.image_url].find(
    (url): url is string => typeof url === "string" && !!url && !failedImages.includes(url)
  );
  const source = scoreSource ?? (anime.community_score != null ? "community_score" : "api_score");
  const score = anime[source];
  const scoreName = source === "community_score" ? "Community score" : "Catalog score";
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((genre) => typeof genre === "string" ? genre : genre.name)
    .filter(Boolean).slice(0, featured ? 3 : 2);
  const metadata = [anime.year, anime.episodes ? `${anime.episodes} ep` : null].filter(Boolean);

  return (
    <Link to={`/anime/${anime.id}`}
      className={cn("catalog-card", compact && "catalog-card--compact", featured && "catalog-card--feature")}>
      <div className="catalog-card__art">
        {artwork ? (
          <img src={artwork} alt="" loading={featured ? "eager" : "lazy"} decoding="async"
            onError={() => setFailedImages((failed) => [...failed, artwork])} />
        ) : (
          <span className="catalog-card__monogram" aria-hidden="true">{title.trim().slice(0, 1)}</span>
        )}
        {score != null && (
          <span className="catalog-card__score" title={scoreName}>
            <Star size={12} fill="currentColor" aria-hidden="true" />
            <span className="sr-only">{scoreName} </span>{score.toFixed(1)}
          </span>
        )}
      </div>
      <div className="catalog-card__caption">
        {metadata.length > 0 && <div className="catalog-card__meta">{metadata.join(" · ")}</div>}
        <h3>{title}</h3>
        {genres.length > 0 && (
          <div className="catalog-card__genres">
            {genres.map((genre) => <span key={genre}>{genre}</span>)}
          </div>
        )}
      </div>
      {featured && <ArrowUpRight size={21} aria-hidden="true" className="catalog-card__open" />}
    </Link>
  );
}
