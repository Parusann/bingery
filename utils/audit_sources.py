"""Source clients for the schedule auditor.

Each source implements `collect(anime_records, window_start, window_end)` and
returns `(claims_by_anime_id, TierHealth)`. Sources are polite by design:

* one shared per-host rate limiter (AniList ≤ ~28 req/min, MAL ~1 req/s,
  Jikan ≤ ~50 req/min) with 429 Retry-After handling;
* every response is cached for the duration of a run (and optionally to a
  JSON file, so re-runs during a debugging session cost zero requests);
* a descriptive User-Agent identifies the auditor;
* official APIs are used everywhere — no scraping.

Independence note: Jikan is an unofficial mirror of MyAnimeList data, so a
Jikan answer is recorded under the same voice name ("myanimelist") and can
never combine with a direct MAL answer to fake two-source confirmation.

`anime_records` are plain dicts: {"id", "anilist_id", "mal_id", "title",
"title_english"} — no ORM objects, so sources are testable without Flask.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from utils.schedule_audit import (
    ST_AIRING,
    ST_CANCELLED,
    ST_FINISHED,
    ST_HIATUS,
    ST_UNKNOWN,
    ST_UPCOMING,
    SourceClaim,
    TierHealth,
)
from utils.dub_sources.crunchyroll import (
    CR_RSS_URL,
    best_match,
    parse_rss,
)
from utils.dub_sources.animeschedule import (
    ANIMESCHEDULE_API_KEY_ENV,
    ANIMESCHEDULE_URL,
    parse_payload,
)

USER_AGENT = (
    "BingeryScheduleAudit/1.0 "
    "(https://github.com/Parusann/bingery-update; schedule accuracy audit)"
)
FETCH_TIMEOUT = 30
MATCH_THRESHOLD = 80.0  # same bar as the ingest pipeline (best_match callers)

_ANILIST_STATUS = {
    "FINISHED": ST_FINISHED,
    "RELEASING": ST_AIRING,
    "NOT_YET_RELEASED": ST_UPCOMING,
    "CANCELLED": ST_CANCELLED,
    "HIATUS": ST_HIATUS,
}
_MAL_STATUS = {
    "finished_airing": ST_FINISHED,
    "currently_airing": ST_AIRING,
    "not_yet_aired": ST_UPCOMING,
}
_JIKAN_STATUS = {
    "finished airing": ST_FINISHED,
    "currently airing": ST_AIRING,
    "not yet aired": ST_UPCOMING,
}
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _weekday_index(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    return _WEEKDAYS.get(raw.strip().lower().rstrip("s"))


class RateLimiter:
    """Minimum-interval limiter per host, shared across sources."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep):
        self._earliest: dict[str, float] = {}
        self._sleep = sleep

    def wait(self, host: str, min_interval: float) -> None:
        now = time.monotonic()
        earliest = self._earliest.get(host, 0.0)
        if now < earliest:
            self._sleep(earliest - now)
            now = time.monotonic()
        self._earliest[host] = now + min_interval


class ResponseCache:
    """In-run response cache, optionally persisted to a JSON file."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self._data: dict[str, dict] = {}
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (OSError, ValueError):
                self._data = {}

    def get(self, key: str):
        hit = self._data.get(key)
        return hit["body"] if hit else None

    def put(self, key: str, body) -> None:
        self._data[key] = {"body": body, "at": datetime.now(timezone.utc).isoformat()}

    def save(self) -> None:
        if not self.path:
            return
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh)


class _Http:
    """Tiny shared HTTP helper: UA, rate limit, cache, one retry on 429."""

    def __init__(self, limiter: RateLimiter, cache: ResponseCache):
        self.limiter = limiter
        self.cache = cache
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def request(
        self,
        method: str,
        url: str,
        *,
        host: str,
        min_interval: float,
        cache_key: Optional[str] = None,
        **kwargs,
    ):
        if cache_key:
            hit = self.cache.get(cache_key)
            if hit is not None:
                return hit, True
        for attempt in (1, 2):
            self.limiter.wait(host, min_interval)
            resp = self.session.request(method, url, timeout=FETCH_TIMEOUT, **kwargs)
            if resp.status_code == 429 and attempt == 1:
                retry_after = float(resp.headers.get("Retry-After") or 5)
                time.sleep(min(retry_after, 60.0))
                continue
            resp.raise_for_status()
            body = resp.json() if "json" in (resp.headers.get("Content-Type") or "") \
                or resp.text[:1].strip() in ("{", "[") else resp.text
            if cache_key:
                self.cache.put(cache_key, body)
            return body, False
        raise RuntimeError("unreachable")


# ─── AniList ─────────────────────────────────────────────────────────────────


class AniListSource:
    """AniList GraphQL — batched by `id_in` / `mediaId_in`, ~28 req/min."""

    name = "anilist"
    HOST = "graphql.anilist.co"
    MIN_INTERVAL = 2.2  # degraded-mode limit is 30 req/min

    def __init__(self, http: _Http):
        self.http = http

    def _gql(self, query: str, variables: dict, cache_key: str):
        return self.http.request(
            "POST",
            "https://graphql.anilist.co",
            host=self.HOST,
            min_interval=self.MIN_INTERVAL,
            cache_key=cache_key,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        )

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name)
        claims: dict[int, list[SourceClaim]] = {}
        by_anilist = {
            a["anilist_id"]: a for a in anime_records if a.get("anilist_id")
        }
        ids = sorted(by_anilist)
        if not ids:
            health.state = "skipped"
            health.detail = "no anilist_id in window"
            return claims, health

        try:
            # 1. Status + total episodes, 50 media per request.
            media_q = """
            query($ids:[Int],$p:Int){Page(page:$p,perPage:50){
              pageInfo{hasNextPage}
              media(id_in:$ids,type:ANIME){id status episodes}}}"""
            for i in range(0, len(ids), 50):
                chunk = ids[i : i + 50]
                body, _ = self._gql(
                    media_q, {"ids": chunk, "p": 1}, f"anilist:media:{chunk}"
                )
                health.requests += 1
                for m in body["data"]["Page"]["media"]:
                    rec = by_anilist.get(m["id"])
                    if not rec:
                        continue
                    claim = SourceClaim(
                        source=self.name,
                        kind="status",
                        track="sub",
                        status=_ANILIST_STATUS.get(m.get("status"), ST_UNKNOWN),
                        total_episodes=m.get("episodes"),
                        detail=f"anilist_id={m['id']} status={m.get('status')}",
                    )
                    claims.setdefault(rec["id"], []).append(claim)
                    health.claims += 1

            # 2. Exact airing timestamps inside the window, batched.
            air_q = """
            query($ids:[Int],$g:Int,$l:Int,$p:Int){Page(page:$p,perPage:50){
              pageInfo{hasNextPage}
              airingSchedules(mediaId_in:$ids,airingAt_greater:$g,
                              airingAt_lesser:$l,sort:TIME){
                mediaId episode airingAt}}}"""
            g = int(start_utc.timestamp())
            l = int(end_utc.timestamp())
            for i in range(0, len(ids), 50):
                chunk = ids[i : i + 50]
                page = 1
                while True:
                    body, _ = self._gql(
                        air_q,
                        {"ids": chunk, "g": g, "l": l, "p": page},
                        f"anilist:air:{chunk}:{g}:{l}:{page}",
                    )
                    health.requests += 1
                    page_data = body["data"]["Page"]
                    for s in page_data["airingSchedules"]:
                        rec = by_anilist.get(s["mediaId"])
                        if not rec:
                            continue
                        claims.setdefault(rec["id"], []).append(
                            SourceClaim(
                                source=self.name,
                                kind="episode_date",
                                track="sub",
                                episode_number=s["episode"],
                                date=datetime.fromtimestamp(
                                    s["airingAt"], tz=timezone.utc
                                ),
                                detail=f"anilist airingSchedule mediaId={s['mediaId']}",
                            )
                        )
                        health.claims += 1
                    if not page_data["pageInfo"]["hasNextPage"]:
                        break
                    page += 1
            health.state = "live"
        except Exception as exc:  # noqa: BLE001 — tier health, not crash
            health.state = "error"
            health.detail = f"{type(exc).__name__}: {exc}"
        return claims, health


# ─── MyAnimeList (official v2, Jikan fallback — ONE voice) ──────────────────


class MalSource:
    """Official MAL API v2 by mal_id; keyless Jikan only when MAL rate-limits.

    Both transports answer as voice "myanimelist" — same underlying data.
    """

    name = "myanimelist"
    MAL_HOST = "api.myanimelist.net"
    JIKAN_HOST = "api.jikan.moe"
    MAL_INTERVAL = 1.0
    JIKAN_INTERVAL = 1.4  # 60/min hard cap, stay under

    def __init__(self, http: _Http, client_id: Optional[str] = None):
        self.http = http
        self.client_id = client_id or os.environ.get("MAL_CLIENT_ID")

    def _fetch_mal(self, mal_id: int):
        body, _ = self.http.request(
            "GET",
            f"https://api.myanimelist.net/v2/anime/{mal_id}"
            "?fields=status,broadcast,start_date,end_date,num_episodes",
            host=self.MAL_HOST,
            min_interval=self.MAL_INTERVAL,
            cache_key=f"mal:{mal_id}",
            headers={"X-MAL-CLIENT-ID": self.client_id},
        )
        return {
            "status": _MAL_STATUS.get(body.get("status"), ST_UNKNOWN),
            "weekday": _weekday_index(
                (body.get("broadcast") or {}).get("day_of_the_week")
            ),
            "total": body.get("num_episodes") or None,
            "end_date": body.get("end_date"),
            "via": "mal",
        }

    def _fetch_jikan(self, mal_id: int):
        body, _ = self.http.request(
            "GET",
            f"https://api.jikan.moe/v4/anime/{mal_id}",
            host=self.JIKAN_HOST,
            min_interval=self.JIKAN_INTERVAL,
            cache_key=f"jikan:{mal_id}",
        )
        data = body.get("data") or {}
        return {
            "status": _JIKAN_STATUS.get(
                (data.get("status") or "").lower(), ST_UNKNOWN
            ),
            "weekday": _weekday_index((data.get("broadcast") or {}).get("day")),
            "total": data.get("episodes") or None,
            "end_date": (data.get("aired") or {}).get("to"),
            "via": "jikan",
        }

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name)
        claims: dict[int, list[SourceClaim]] = {}
        if not self.client_id:
            health.state = "dark"
            health.detail = "MAL_CLIENT_ID missing — falling back to Jikan only"
        jikan_fallbacks = 0
        errors = 0
        key_rejected = False
        for rec in anime_records:
            mal_id = rec.get("mal_id")
            if not mal_id:
                continue
            info = None
            if self.client_id:
                try:
                    info = self._fetch_mal(mal_id)
                    health.requests += 1
                except requests.HTTPError as exc:
                    sc = exc.response.status_code if exc.response is not None else 0
                    if sc == 429:
                        jikan_fallbacks += 1
                    elif sc in (401, 403):
                        # Bad/expired client id — this is a credentials
                        # problem, not rate limiting; surface it as degraded.
                        key_rejected = True
                        jikan_fallbacks += 1
                    elif sc == 404:
                        continue  # MAL doesn't know this id — nothing to claim
                    else:
                        errors += 1
                        continue
                except requests.RequestException:
                    errors += 1
                    continue
            if info is None:
                try:
                    info = self._fetch_jikan(mal_id)
                    health.requests += 1
                except Exception:  # noqa: BLE001
                    errors += 1
                    continue
            entry_claims = [
                SourceClaim(
                    source=self.name,
                    kind="status",
                    track="sub",
                    status=info["status"],
                    total_episodes=info["total"],
                    detail=f"mal_id={mal_id} via={info['via']} end={info['end_date']}",
                )
            ]
            if info["weekday"] is not None:
                entry_claims.append(
                    SourceClaim(
                        source=self.name,
                        kind="weekly_slot",
                        track="sub",
                        jst_weekday=info["weekday"],
                        detail=f"broadcast weekday (JST) via={info['via']}",
                    )
                )
            claims.setdefault(rec["id"], []).extend(entry_claims)
            health.claims += len(entry_claims)
        if health.state != "dark":
            if not any(rec.get("mal_id") for rec in anime_records):
                health.state = "skipped"
                health.detail = "no mal_id in window"
            elif key_rejected:
                health.state = "degraded"
                health.detail = (
                    "MAL client id rejected (401/403) — Jikan answered "
                    "instead; fix MAL_CLIENT_ID"
                )
            else:
                health.state = "live" if health.requests else "error"
        parts = []
        if jikan_fallbacks:
            parts.append(f"{jikan_fallbacks} Jikan fallbacks")
        if errors:
            parts.append(f"{errors} fetch errors")
        if parts:
            health.detail = (health.detail + "; " if health.detail else "") + ", ".join(parts)
        return claims, health


# ─── AnimeSchedule.net (dub timetable — needs API key) ──────────────────────


class AnimeScheduleSource:
    name = "animeschedule"
    HOST = "animeschedule.net"
    MIN_INTERVAL = 1.5

    def __init__(self, http: _Http, api_key: Optional[str] = None):
        self.http = http
        self.api_key = api_key or os.environ.get(ANIMESCHEDULE_API_KEY_ENV)

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name)
        claims: dict[int, list[SourceClaim]] = {}
        if not self.api_key:
            health.state = "dark"
            health.detail = f"{ANIMESCHEDULE_API_KEY_ENV} not set — tier dark (401)"
            return claims, health
        try:
            body, _ = self.http.request(
                "GET",
                ANIMESCHEDULE_URL,
                host=self.HOST,
                min_interval=self.MIN_INTERVAL,
                cache_key="animeschedule:dub",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            health.requests += 1
            text = body if isinstance(body, str) else json.dumps(body)
            entries = parse_payload(text)
            candidates = _CandidateShims(anime_records)
            for entry in entries:
                if entry.episode_number is None:
                    continue
                shim, score = best_match(
                    entry.english_title or entry.title, candidates.shims
                )
                if shim is None or score < MATCH_THRESHOLD:
                    continue
                date = entry.air_date
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                claims.setdefault(shim.record["id"], []).append(
                    SourceClaim(
                        source=self.name,
                        kind="episode_date",
                        track="dub",
                        episode_number=entry.episode_number,
                        date=date,
                        match_confidence=score,
                        detail=f"dub timetable title={entry.title!r}",
                    )
                )
                health.claims += 1
                # Presence in the dub timetable is evidence the dub is running.
                claims[shim.record["id"]].append(
                    SourceClaim(
                        source=self.name,
                        kind="status",
                        track="dub",
                        status=ST_AIRING,
                        match_confidence=score,
                        detail="listed in dub timetable",
                    )
                )
            health.state = "live"
        except requests.HTTPError as exc:
            sc = exc.response.status_code if exc.response is not None else 0
            health.state = "dark" if sc in (401, 403) else "error"
            health.detail = f"HTTP {sc} from timetable endpoint"
        except Exception as exc:  # noqa: BLE001
            health.state = "error"
            health.detail = f"{type(exc).__name__}: {exc}"
        return claims, health


# ─── Crunchyroll RSS (dub premieres) ─────────────────────────────────────────


class CrunchyrollSource:
    name = "crunchyroll_rss"
    HOST = "feeds.feedburner.com"
    MIN_INTERVAL = 2.0

    def __init__(self, http: _Http, url: str = CR_RSS_URL):
        self.http = http
        self.url = url

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name)
        claims: dict[int, list[SourceClaim]] = {}
        try:
            body, _ = self.http.request(
                "GET",
                self.url,
                host=self.HOST,
                min_interval=self.MIN_INTERVAL,
                cache_key="crunchyroll:rss",
            )
            health.requests += 1
            xml_text = body if isinstance(body, str) else json.dumps(body)
            entries = parse_rss(xml_text)
            candidates = _CandidateShims(anime_records)
            for entry in entries:
                if entry.episode_number is None:
                    continue
                shim, score = best_match(entry.show_title, candidates.shims)
                if shim is None or score < MATCH_THRESHOLD:
                    continue
                date = entry.pub_date
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                claims.setdefault(shim.record["id"], []).append(
                    SourceClaim(
                        source=self.name,
                        kind="episode_date",
                        track="dub",
                        episode_number=entry.episode_number,
                        date=date,
                        match_confidence=score,
                        detail=f"RSS item {entry.show_title!r}",
                    )
                )
                health.claims += 1
            health.state = "live"
        except requests.HTTPError as exc:
            sc = exc.response.status_code if exc.response is not None else 0
            health.state = "error"
            health.detail = f"HTTP {sc} fetching feed"
        except Exception as exc:  # noqa: BLE001
            health.state = "error"
            health.detail = f"{type(exc).__name__}: {exc}"
        return claims, health


class _Shim:
    """Adapter so best_match (which expects .title/.title_english/.status/
    .year/.season attributes on Anime rows) can score plain dict records."""

    def __init__(self, record: dict):
        self.record = record
        self.title = record.get("title")
        self.title_english = record.get("title_english")
        self.status = record.get("status")
        self.year = record.get("year")
        self.season = record.get("season")


class _CandidateShims:
    def __init__(self, anime_records):
        self.shims = [_Shim(r) for r in anime_records]


# ─── Attended web research (file-injected, never automated) ─────────────────


class ResearchFileSource:
    """Claims gathered by attended web research, loaded from a JSON file.

    Format: [{"anime_id": 12, "track": "dub", "episode_number": 5,
              "date": "2026-07-14", "date_only": true, "status": null,
              "confidence": 95, "detail": "<url / reasoning>"}]

    The CI cron never sets --research-file; this source exists so a human-
    supervised run can feed verified findings into the same classification
    machinery with provenance recorded.
    """

    name = "web_research"

    def __init__(self, path: Optional[str]):
        self.path = path

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name)
        claims: dict[int, list[SourceClaim]] = {}
        if not self.path:
            health.state = "skipped"
            health.detail = "attended-only source; no research file supplied"
            return claims, health
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
            for row in rows:
                date = None
                if row.get("date"):
                    date = datetime.fromisoformat(row["date"])
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                claims.setdefault(int(row["anime_id"]), []).append(
                    SourceClaim(
                        source=self.name,
                        kind="status" if row.get("status") else "episode_date",
                        track=row.get("track", "dub"),
                        episode_number=row.get("episode_number"),
                        date=date,
                        date_only=bool(row.get("date_only", True)),
                        status=row.get("status"),
                        match_confidence=float(row.get("confidence", 90)),
                        detail=row.get("detail", ""),
                    )
                )
                health.claims += 1
            health.state = "live"
        except Exception as exc:  # noqa: BLE001
            health.state = "error"
            health.detail = f"{type(exc).__name__}: {exc}"
        return claims, health


def default_sources(
    *,
    cache_path: Optional[str] = None,
    research_file: Optional[str] = None,
    mal_client_id: Optional[str] = None,
    animeschedule_key: Optional[str] = None,
):
    """The standard tier stack, sharing one limiter + cache."""
    http = _Http(RateLimiter(), ResponseCache(cache_path))
    return [
        AniListSource(http),
        MalSource(http, client_id=mal_client_id),
        AnimeScheduleSource(http, api_key=animeschedule_key),
        CrunchyrollSource(http),
        ResearchFileSource(research_file),
    ], http
