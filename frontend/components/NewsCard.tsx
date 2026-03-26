"use client";

import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";

type NewsCardProps = {
  title: string;
  source: string;
  url: string;
  snippet?: string | null;
  publishedAt?: string | null;
  index?: number;
};

export function NewsCard({ title, source, url, snippet, publishedAt, index = 0 }: NewsCardProps) {
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
        <span className="data-font text-[10px] sm:text-xs font-semibold uppercase tracking-[0.26em] text-[var(--teal)]">
          {source}
        </span>
        <div className="flex items-center gap-3">
          {publishedAt && (
            <span className="data-font text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">
              {new Date(publishedAt).toLocaleDateString()}
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
    </motion.a>
  );
}
