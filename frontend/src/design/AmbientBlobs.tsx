// Static decorative blobs. These used to drift forever via framer-motion,
// but animating a 160px-blurred element behind the app's backdrop-filter
// glass forced every glass surface to re-rasterize its blur on EVERY frame
// (continuous full-screen repaint = major scroll/interaction jank). A 160px
// blur that doesn't move is a one-time raster the compositor caches, so the
// look is preserved at effectively zero ongoing cost.
export function AmbientBlobs() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 overflow-hidden z-0"
    >
      <div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 720,
          height: 720,
          left: "-20%",
          top: "-30%",
          background:
            "radial-gradient(closest-side, rgba(230,166,128,0.45), rgba(230,166,128,0) 70%)",
        }}
      />
      <div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 640,
          height: 640,
          right: "-15%",
          bottom: "-25%",
          background:
            "radial-gradient(closest-side, rgba(184,154,196,0.30), rgba(184,154,196,0) 70%)",
        }}
      />
    </div>
  );
}
