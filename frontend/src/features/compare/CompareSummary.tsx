import { Link } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { Badge } from "@/design/Badge";
import type { AnimeCompareResponse, AnimeCompareSide } from "@/types/models";

// Side-by-side comparison of two anime + the user's own ratings.
//
// Shared genres are highlighted on each side with an "amber" badge tone;
// unique-to-this-side genres get a neutral badge. The shared/unique
// breakdown panel at the bottom calls out how much the two anime overlap.

function Side({ side, sharedGenres }: { side: AnimeCompareSide; sharedGenres: Set<string> }) {
  const a = side.anime;
  const display = a.title_english || a.title;
  const score = a.api_score?.toFixed(1) ?? "—";
  const community = a.community_score?.toFixed(1);
  return (
    <GlassCard tone="warm" className="p-5 space-y-4">
      <Link
        to={`/anime/${a.id}`}
        className="flex gap-3 items-start group"
      >
        {a.image_url ? (
          <img
            src={a.image_url}
            alt=""
            className="w-20 h-28 object-cover rounded-md shadow-md shrink-0"
          />
        ) : (
          <div className="w-20 h-28 rounded-md bg-white/5 shrink-0" />
        )}
        <div className="min-w-0">
          <div className="font-display text-xl leading-tight group-hover:text-amber line-clamp-3">
            {display}
          </div>
          <div className="text-xs text-text-muted mt-1">
            {a.year ?? "—"} · {a.episodes ?? "?"} eps
          </div>
          <div className="text-sm mt-2">
            <span className="text-text-muted">Public</span>{" "}
            <span className="font-mono">★ {score}</span>
            {community ? (
              <>
                {"  ·  "}
                <span className="text-text-muted">Community</span>{" "}
                <span className="font-mono">★ {community}</span>
              </>
            ) : null}
          </div>
          {a.studio ? (
            <div className="text-xs text-text-muted mt-1">
              Studio: <span className="text-text">{a.studio}</span>
            </div>
          ) : null}
        </div>
      </Link>

      <div>
        <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
          Genres
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(a.official_genres ?? []).map((g) => (
            <Badge
              key={g.name}
              color={sharedGenres.has(g.name) ? "#e6a680" : "#94a3b8"}
            >
              {g.name}
            </Badge>
          ))}
          {(a.official_genres ?? []).length === 0 ? (
            <span className="text-xs text-text-muted">none</span>
          ) : null}
        </div>
      </div>

      <div>
        <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-2">
          Your take
        </div>
        {side.user.score != null ? (
          <div className="text-sm">
            You rated this <span className="font-mono text-amber">{side.user.score}/10</span>
            {side.user.review ? (
              <div className="text-text-muted italic mt-1 line-clamp-2">
                "{side.user.review}"
              </div>
            ) : null}
          </div>
        ) : (
          <div className="text-sm text-text-muted">
            You haven't rated this yet.
          </div>
        )}
      </div>
    </GlassCard>
  );
}

export function CompareSummary({ data }: { data: AnimeCompareResponse }) {
  const sharedSet = new Set(data.shared.official_genres);
  const aOnly = data.unique.a_only_official_genres;
  const bOnly = data.unique.b_only_official_genres;
  const overlap = data.shared.official_genres.length;
  const total = overlap + aOnly.length + bOnly.length;
  const overlapPct = total > 0 ? Math.round((overlap / total) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="grid sm:grid-cols-2 gap-4">
        <Side side={data.a} sharedGenres={sharedSet} />
        <Side side={data.b} sharedGenres={sharedSet} />
      </div>

      <GlassCard tone="warm" className="p-5">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-display text-xl">Overlap</h2>
          <span className="text-sm text-text-muted">
            {overlapPct}% genre match · {overlap} shared
          </span>
        </div>
        <div className="grid sm:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-1">
              Shared genres
            </div>
            {data.shared.official_genres.length ? (
              <div className="flex flex-wrap gap-1.5">
                {data.shared.official_genres.map((g) => (
                  <Badge key={g} color="#e6a680">{g}</Badge>
                ))}
              </div>
            ) : (
              <div className="text-text-muted">No overlap.</div>
            )}
          </div>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-1">
              A only
            </div>
            {aOnly.length ? (
              <div className="flex flex-wrap gap-1.5">
                {aOnly.map((g) => (
                  <Badge key={g} color="#94a3b8">{g}</Badge>
                ))}
              </div>
            ) : (
              <div className="text-text-muted">—</div>
            )}
          </div>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-text-muted mb-1">
              B only
            </div>
            {bOnly.length ? (
              <div className="flex flex-wrap gap-1.5">
                {bOnly.map((g) => (
                  <Badge key={g} color="#94a3b8">{g}</Badge>
                ))}
              </div>
            ) : (
              <div className="text-text-muted">—</div>
            )}
          </div>
        </div>
        {data.shared.studios.length ? (
          <div className="text-sm text-text-muted mt-4">
            Same studio:{" "}
            <span className="text-text font-medium">
              {data.shared.studios.join(", ")}
            </span>
          </div>
        ) : null}
      </GlassCard>
    </div>
  );
}
