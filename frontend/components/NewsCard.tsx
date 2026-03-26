"use client";

import { motion } from "framer-motion";

type NewsCardProps = {
  title: string;
  source: string;
  url: string;
  publishedAt?: string | null;
};

export function NewsCard({ title, source, url, publishedAt }: NewsCardProps) {
  return (
    <motion.a
      href={url}
      target="_blank"
      rel="noreferrer"
      whileHover={{ y: -4, scale: 1.01 }}
      whileTap={{ scale: 0.985 }}
      className="block rounded-[30px] border border-[rgba(23,49,58,0.08)] bg-[rgba(255,250,242,0.88)] p-5 shadow-[var(--shadow-outer),inset_4px_4px_10px_rgba(0,0,0,0.08)] transition-transform"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="data-font text-xs uppercase tracking-[0.26em] text-[var(--teal)]">{source}</span>
        {publishedAt ? (
          <span className="data-font text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">
            {new Date(publishedAt).toLocaleDateString()}
          </span>
        ) : null}
      </div>
      <p className="text-base font-medium leading-6">{title}</p>
    </motion.a>
  );
}
