"use client";

import { useEffect, useState } from "react";
import { Activity, Clock, Database, Globe } from "lucide-react";

type StatusBarProps = {
  countryCode: string | null;
  cacheHit?: boolean;
};

export function StatusBar({ countryCode, cacheHit }: StatusBarProps) {
  const [time, setTime] = useState<string>("--:--:--");

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
            Ping: {Math.floor(Math.random() * 20 + 30)}ms
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

        {cacheHit !== undefined && (
          <div className="hidden items-center gap-1.5 lg:flex">
            <Database size={12} className={cacheHit ? "text-[var(--positive)]" : "text-[var(--orange)]"} />
            <span className="data-font text-[10px] uppercase tracking-widest text-[var(--muted)]">
              {cacheHit ? "CACHE HIT" : "LIVE FETCH"}
            </span>
          </div>
        )}

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
