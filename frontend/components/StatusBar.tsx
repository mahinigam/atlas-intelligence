"use client";

import { useEffect, useState } from "react";
import { Activity, Clock, Database, Globe } from "lucide-react";
import { PipelineStatus, ProviderStatus, SummaryStatus } from "@/lib/types";

type StatusBarProps = {
  countryCode: string | null;
  providerStatuses?: ProviderStatus[];
  summaryStatus?: SummaryStatus | null;
  pipelineStatus?: PipelineStatus[];
  articleCacheHit?: boolean;
  summaryCacheHit?: boolean;
};

export function StatusBar({
  countryCode,
  providerStatuses = [],
  summaryStatus = null,
  pipelineStatus = [],
  articleCacheHit,
  summaryCacheHit,
}: StatusBarProps) {
  const [time, setTime] = useState<string>("--:--:--");

  const providerUnavailable = providerStatuses.some((status) =>
    ["quota_exhausted", "unavailable", "timeout", "cooldown"].includes(status.status)
  );
  const providerLabel = providerUnavailable ? "NEWS UNAVAILABLE" : "NEWS READY";
  const summaryLabel = summaryStatus?.used_ai ? "AI SUMMARY" : "AI REQUIRED";
  const summaryUsageLabel =
    summaryStatus?.used_ai && summaryStatus.total_tokens
      ? `${summaryStatus.total_tokens} TOK`
      : null;

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toISOString().slice(11, 19) + " UTC");
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 flex h-9 items-center justify-between border-t border-[rgba(23,49,58,0.08)] bg-[rgba(242,235,217,0.95)] px-4 shadow-[0_-4px_12px_rgba(0,0,0,0.03)] backdrop-blur-xl">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className="relative flex h-2 w-2 items-center justify-center">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--positive)] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--positive)]" />
          </div>
          <span className="data-font text-[10px] uppercase tracking-widest text-[var(--text-soft)]">
            SYSTEM ONLINE
          </span>
        </div>
        
        <div className="hidden items-center gap-1.5 md:flex">
          <Activity size={12} className="text-[var(--teal)]" />
          <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
            Ping: 42ms
          </span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {countryCode && (
          <div className="hidden items-center gap-1.5 md:flex">
            <Globe size={12} className="text-[var(--orange)]" />
            <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
              LOC: {countryCode}
            </span>
          </div>
        )}

        {articleCacheHit !== undefined && (
          <div className="hidden items-center gap-1.5 lg:flex">
            <Database
              size={12}
              className={articleCacheHit || summaryCacheHit ? "text-[var(--positive)]" : "text-[var(--orange)]"}
            />
            <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
              {articleCacheHit || summaryCacheHit ? "CACHE ACTIVE" : "LIVE FETCH"}
            </span>
          </div>
        )}

        <div className="hidden items-center gap-1.5 lg:flex">
          <Activity size={12} className={providerUnavailable ? "text-[var(--orange)]" : "text-[var(--teal)]"} />
          <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
            {providerLabel}
          </span>
        </div>

        <div className="hidden items-center gap-1.5 lg:flex">
          <Activity
            size={12}
            className={summaryStatus?.used_ai ? "text-[var(--positive)]" : "text-[var(--orange)]"}
          />
          <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
            {summaryUsageLabel ? `${summaryLabel} ${summaryUsageLabel}` : summaryLabel}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Clock size={12} className="text-[var(--teal-soft)]" />
          <span className="data-font text-[10px] uppercase tracking-widest text-[var(--text-soft)]">
            {time}
          </span>
        </div>
      </div>
    </footer>
  );
}
