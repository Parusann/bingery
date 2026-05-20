/**
 * LandingPage renders the hand-designed HTML mockup verbatim from
 * `/landing.html` (served by Vite from `frontend/public/`). We use a
 * full-viewport iframe positioned over AppShell so every flourish in the
 * mockup — Spline 3D, three.js liquid shader, cmd-K palette, scroll reveals,
 * mouse spotlight, counter animations, sound effects — runs natively without
 * needing to be reimplemented in React.
 *
 * Internal links inside the mockup navigate the parent React Router via the
 * `<base target="_top">` injected into `landing.html`.
 */
export function LandingPage() {
  return (
    <div className="fixed inset-0 z-50 bg-bg">
      <iframe
        src="/landing.html"
        title="Bingery — Discover what you'll actually love"
        className="w-full h-full border-0 block"
        // Allow the iframe to use modern browser features the mockup uses
        // (spline-viewer, three.js, audio).
        allow="autoplay; fullscreen; xr-spatial-tracking"
      />
    </div>
  );
}
