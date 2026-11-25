import { useState } from "react";
import { ArrowRight, ArrowUpRight, CalendarDays, ChevronLeft, ChevronRight, Clapperboard, Layers, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useAnimeList } from "@/hooks/useAnimeList";
import { useAuth } from "@/stores/auth";
import { AnimeCard } from "@/features/discover/AnimeCard";
import { films } from "./films";
import "./landing.css";

const shortcuts = [
  { to: "/schedule", title: "Release calendar", text: "See which subbed and dubbed episodes air this week.", icon: CalendarDays },
  { to: "/watchlist", title: "Your watchlist", text: "Keep your place in each series and save titles for later.", icon: Layers },
  { to: "/for-you", title: "Made for you", text: "Find recommendations based on the anime you rate.", icon: Sparkles },
];

export function LandingPage() {
  const [index, setIndex] = useState(0);
  const film = films[index];
  const user = useAuth((s) => s.user);
  const { data, isLoading, isError, isFetching, refetch } = useAnimeList({ perPage: 6 });
  const filmSearch = film.searchTerm ?? film.title;

  return (
    <div className="landing">
      <section className="landing-hero" aria-labelledby="landing-title">
        <img
          className="landing-still" src={film.image} alt={film.alt}
          width={1920} height={1038} style={{ objectPosition: film.position }}
        />
        <div className="landing-intro">
          <h1 id="landing-title">Discover what<br />you’ll <em>actually love.</em></h1>
          <p>Find your next anime, keep track of every episode, and build a watchlist that feels like you.</p>
          <div className="landing-actions">
            <Link className="landing-primary" to="/discover">Browse anime <ArrowRight size={17} /></Link>
            <Link className="landing-secondary" to="/chat"><Sparkles size={16} /> Ask the guide</Link>
          </div>
        </div>
        <div className="landing-filmbar">
          <div className="landing-film" aria-live="polite" aria-atomic="true">
            <span className="landing-meta"><Clapperboard size={14} aria-hidden="true" /> Film spotlight <span aria-hidden="true">/</span> {film.year}</span>
            <Link to={`/discover?q=${encodeURIComponent(filmSearch)}`}>{film.title} <ArrowUpRight size={16} /></Link>
          </div>
          <div className="landing-film-controls">
            <button type="button" aria-label="Previous spotlight film" onClick={() => setIndex((i) => (i - 1 + films.length) % films.length)}><ChevronLeft size={19} /></button>
            <button type="button" aria-label="Next spotlight film" onClick={() => setIndex((i) => (i + 1) % films.length)}><ChevronRight size={19} /></button>
          </div>
        </div>
      </section>
      <a className="landing-credit" href={`https://www.ghibli.jp/works/${film.gallery}/`}>{film.credit}</a>

      <section className="landing-section" aria-labelledby="landing-top">
        <div className="landing-section-head">
          <h2 id="landing-top">Top rated anime</h2>
          <Link to="/discover?sort=api_score">View catalog <ArrowRight size={16} /></Link>
        </div>
        {data?.anime.length ? (
          <div className="landing-shelf">
            {data.anime.map((anime) => <AnimeCard key={anime.id} anime={anime} compact scoreSource="api_score" />)}
          </div>
        ) : isLoading ? (
          <div className="landing-shelf" aria-label="Loading top rated anime" aria-busy="true">
            {Array.from({ length: 6 }, (_, n) => <div key={n} className="landing-placeholder" />)}
          </div>
        ) : (
          <div className="landing-shelf-state">
            <p>{isError ? "The catalog couldn’t load." : "Anime will appear here as the catalog fills up."}</p>
            {isError && <button type="button" disabled={isFetching} onClick={() => void refetch()}>Try again</button>}
          </div>
        )}
      </section>

      <section className="landing-section" aria-labelledby="landing-library">
        <div className="landing-section-head"><h2 id="landing-library">Plan your next watch</h2></div>
        <div className="landing-shortcuts">
          {shortcuts.map(({ to, title, text, icon: Icon }) => (
            <Link to={to} key={to}>
              <Icon size={22} strokeWidth={1.5} className="landing-shortcut-icon" />
              <div><h3>{title}</h3><p>{text}</p></div>
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          ))}
        </div>
      </section>
      {!user && (
        <footer className="landing-footer">
          <p>Want a Bingery account?</p>
          <Link to="/auth?mode=waitlist">Join the waitlist <ArrowRight size={16} /></Link>
        </footer>
      )}
    </div>
  );
}
