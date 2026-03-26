"use client";

import { motion } from "framer-motion";

type TimeTravelSliderProps = {
  daysBack: number;
  onChange: (days: number) => void;
};

export function TimeTravelSlider({ daysBack, onChange }: TimeTravelSliderProps) {
  const ticks = [0, 3, 7, 14, 30];

  return (
    <section className="panel px-4 py-5 md:px-8 md:py-6">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p className="data-font text-[10px] sm:text-xs font-semibold uppercase tracking-[0.32em] text-[var(--teal-soft)]">
            Time-Travel Dial
          </p>
          <h2 className="mt-1 text-lg sm:text-xl font-bold tracking-tight text-[var(--text)]">
            Historical Event Window
          </h2>
        </div>
        
        {/* Retro LCD Display */}
        <div className="rounded-xl border-2 border-[rgba(23,49,58,0.08)] bg-[rgba(23,49,58,0.04)] px-4 py-2 shadow-[inset_2px_2px_8px_rgba(0,0,0,0.05)]">
          <motion.span 
             key={daysBack}
             initial={{ opacity: 0.5, y: -4 }}
             animate={{ opacity: 1, y: 0 }}
             className="data-font text-sm font-bold text-[var(--orange)]"
          >
            {daysBack === 0 ? "LIVE PULSE" : `T-${daysBack} DAYS`}
          </motion.span>
        </div>
      </div>

      <div className="relative px-2">
        <input
          aria-label="Time travel slider"
          className="range-track relative z-10"
          type="range"
          min={0}
          max={30}
          step={1}
          value={daysBack}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        
        <div className="mt-4 flex justify-between px-1">
          {ticks.map((tick) => (
            <div key={tick} className="flex flex-col items-center">
              <div className="mb-1.5 h-1.5 w-[2px] rounded-full bg-[rgba(23,49,58,0.2)]" />
              <span className="data-font text-[9px] uppercase tracking-[0.22em] text-[var(--muted)]">
                {tick === 0 ? "NOW" : `${tick}D`}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
