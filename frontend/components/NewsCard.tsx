"use client";

import { motion } from "framer-motion";
import { ExternalLink, Clock, Shield, Tag } from "lucide-react";

type NewsCardProps = {
  title: string;
  source: string;
  provider: string;
  providers?: string[];
  url: string;
  snippet?: string | null;
  publishedAt?: string | null;
  isPreferredSource?: boolean;
  confidence?: string;
  category?: string;
  evidencePoints?: string[];
  matchedTerms?: string[];
  index?: number;
};

function confidenceColor(confidence: string): string {
  switch (confidence) {
    case "high":
      return "var(--positive)";
    case "medium":
      return "var(--orange)";
    case "low":
      return "var(--negative)";
    default:
      return "var(--muted)";
  }
}

function relativeFreshness(publishedAt: string | null | undefined): string | null {
  if (!publishedAt) return null;
  const now = Date.now();
  const published = new Date(publishedAt).getTime();
  const diffMs = now - published;
  if (diffMs < 0) return "just now";
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  if (hours < 1) return `${Math.max(1, Math.floor(diffMs / (1000 * 60)))}m ago`;
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NewsCard({
  title,
  source,
  provider,
  providers,
  url,
  snippet,
  publishedAt,
  isPreferredSource = false,
  confidence = "medium",
  category = "general",
  evidencePoints = [],
  matchedTerms = [],
  index = 0,
}: NewsCardProps) {
  const freshness = relativeFreshness(publishedAt);

  return (
    <motion.a
      href={url}
      target="_blank"
      rel="noreferrer"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: "easeOut" }}
      whileHover={{ y: -4, scale: 1.01 }}
      whileTap={{ scale: 0.985 }}
      className="clay-card group block p-5 transition-transform"
    >
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-[rgba(23,49,58,0.06)] pb-3">
        <div className="flex flex-col gap-1">
          <span className="data-font text-[10px] sm:text-xs font-semibold uppercase tracking-[0.26em] text-[var(--teal)]">
            {source}
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="data-font text-[9px] uppercase tracking-[0.2em] text-[var(--muted)]">
              {providers?.length ? providers.join(" + ") : provider}
              {isPreferredSource ? " • ★ preferred" : ""}
            </span>
            <span className="data-font text-[9px] uppercase tracking-[0.2em] text-[var(--muted)]">
              {category}
            </span>
            {/* Confidence badge */}
            <span
              className="data-font text-[9px] font-bold uppercase tracking-[0.18em] px-1.5 py-0.5 rounded-full flex items-center gap-1"
              style={{
                backgroundColor: `color-mix(in srgb, ${confidenceColor(confidence)} 12%, transparent)`,
                color: confidenceColor(confidence),
              }}
            >
              <Shield size={8} />
              {confidence}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Freshness badge */}
          {freshness && (
            <span className="data-font text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--teal-soft)] flex items-center gap-1 bg-[rgba(23,49,58,0.04)] rounded-full px-2 py-0.5">
              <Clock size={9} />
              {freshness}
            </span>
          )}
          <ExternalLink size={14} className="text-[var(--orange)] opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      </div>
      
      <p className="text-[15px] sm:text-base font-semibold leading-relaxed tracking-tight text-[var(--text)]">
        {title}
      </p>

      {snippet && (
        <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-[var(--text-soft)]">
          {snippet}
        </p>
      )}

      {/* Matched terms as keyword pills */}
      {!!matchedTerms.length && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {matchedTerms.slice(0, 5).map((term) => (
            <span
              key={term}
              className="data-font text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--teal-soft)] bg-[rgba(23,49,58,0.05)] rounded-full px-2 py-0.5 flex items-center gap-1"
            >
              <Tag size={8} />
              {term}
            </span>
          ))}
        </div>
      )}

      {!!evidencePoints.length && (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--muted)]">
          Why relevant: {evidencePoints[0]}
        </p>
      )}
    </motion.a>
  );
}
