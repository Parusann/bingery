import type { CompareTaste } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

export function TasteVenn({ taste, aLabel, bLabel }: { taste: CompareTaste; aLabel: string; bLabel: string }) {
  const shared = taste.shared_genres.length;
  const only_a = taste.only_a_genres.length;
  const only_b = taste.only_b_genres.length;
  return (
    <GlassCard tone="warm" className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Taste overlap</h2>
        <span className="text-sm text-text-muted">
          Agreement: {(taste.score_agreement * 100).toFixed(0)}%
        </span>
      </div>
      <div className="relative h-56 flex items-center justify-center">
        <svg
          viewBox="0 0 400 200"
          className="w-full h-full max-w-md"
          aria-label="Venn diagram"
        >
          <circle
            cx="140"
            cy="100"
            r="80"
            fill="rgba(230,166,128,0.25)"
            stroke="rgba(230,166,128,0.5)"
            strokeWidth="1.5"
          />
          <circle
            cx="260"
            cy="100"
            r="80"
            fill="rgba(184,154,196,0.25)"
            stroke="rgba(184,154,196,0.5)"
            strokeWidth="1.5"
          />
          <text x="80" y="108" fontSize="14" fill="rgba(230,166,128,0.95)" fontFamily="Fraunces, serif">
            {aLabel}: {only_a}
          </text>
          <text x="200" y="108" fontSize="14" fill="rgba(255,255,255,0.9)" textAnchor="middle" fontFamily="Fraunces, serif">
            shared: {shared}
          </text>
          <text x="320" y="108" fontSize="14" fill="rgba(184,154,196,0.95)" textAnchor="end" fontFamily="Fraunces, serif">
            {bLabel}: {only_b}
          </text>
        </svg>
      </div>
    </GlassCard>
  );
}
