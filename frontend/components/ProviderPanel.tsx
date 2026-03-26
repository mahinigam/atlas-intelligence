"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, Activity, Zap, Clock, AlertTriangle } from "lucide-react";
import type { ProviderStatus } from "@/lib/types";

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  worldnews: "World News API",
  currents: "Currents API",
  newscatcher: "NewsCatcher",
  newsapi_org: "NewsAPI.org",
  gnews: "GNews",
  newsdata: "NewsData.io",
};

function statusColor(status: string): string {
  switch (status) {
    case "ok":
      return "var(--positive)";
    case "empty":
      return "var(--orange)";
    case "cooldown":
    case "quota_exhausted":
      return "var(--negative)";
    case "unconfigured":
      return "var(--muted)";
    default:
      return "var(--orange)";
  }
}

function statusDot(status: string): string {
  if (status === "ok") return "🟢";
  if (status === "empty") return "🟡";
  if (status === "cooldown" || status === "quota_exhausted" || status === "unavailable" || status === "timeout")
    return "🔴";
  return "⚪";
}

export function ProviderPanel({
  providerStatuses,
}: {
  providerStatuses?: ProviderStatus[];
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!providerStatuses?.length) return null;

  const healthy = providerStatuses.filter((p) => p.healthy).length;
  const total = providerStatuses.length;
  const allHealthy = healthy === total;

  return (
    <div className="rounded-[28px] border border-[rgba(23,49,58,0.08)] bg-[rgba(255,255,255,0.45)] overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-5 py-4 transition-colors hover:bg-[rgba(255,248,237,0.3)]"
      >
        <div className="flex items-center gap-3">
          <Activity
            size={16}
            className={allHealthy ? "text-[var(--positive)]" : "text-[var(--orange)]"}
          />
          <span className="data-font text-[10px] font-bold uppercase tracking-[0.28em] text-[var(--teal-soft)]">
            Provider Health
          </span>
          <span
            className="data-font text-[10px] font-bold uppercase tracking-[0.2em] px-2 py-0.5 rounded-full"
            style={{
              backgroundColor: allHealthy
                ? "rgba(33, 140, 104, 0.1)"
                : "rgba(229, 124, 48, 0.1)",
              color: allHealthy ? "var(--positive)" : "var(--orange)",
            }}
          >
            {healthy}/{total} Active
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp size={16} className="text-[var(--muted)]" />
        ) : (
          <ChevronDown size={16} className="text-[var(--muted)]" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4 grid gap-2">
              {providerStatuses.map((ps) => (
                <div
                  key={ps.provider}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-[rgba(23,49,58,0.06)] bg-[rgba(255,250,244,0.7)] px-4 py-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-sm flex-shrink-0">{statusDot(ps.status)}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--text)] truncate">
                        {PROVIDER_DISPLAY_NAMES[ps.provider] ?? ps.provider}
                      </p>
                      <p className="text-[11px] text-[var(--muted)] truncate mt-0.5">
                        {ps.message}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {ps.articles_returned > 0 && (
                      <span className="data-font text-[10px] font-bold text-[var(--teal)] bg-[rgba(23,49,58,0.04)] rounded-full px-2 py-0.5">
                        {ps.articles_returned} articles
                      </span>
                    )}
                    {ps.cache_hit && (
                      <span className="data-font text-[10px] font-bold text-[var(--orange)] flex items-center gap-1">
                        <Zap size={10} /> cached
                      </span>
                    )}
                    {ps.cooldown_until && (
                      <span className="data-font text-[10px] font-bold text-[var(--negative)] flex items-center gap-1">
                        <Clock size={10} /> cooldown
                      </span>
                    )}
                    {!ps.healthy && !ps.cooldown_until && (
                      <AlertTriangle size={14} className="text-[var(--negative)]" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
